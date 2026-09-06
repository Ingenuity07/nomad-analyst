"""
Kite Credential and Authentication Lifecycle Service.

Manages the daily personal Kite Connect 2FA authentication workflow:
1. Generate Zerodha login URL (with manual 2FA on Kite portal)
2. Capture request_token from callback URL
3. Exchange request_token for access_token server-side using Kite API secret
4. Encrypt and persist access_token at rest in KiteCredential
5. Enforce daily 06:00 IST expiry rules
6. Serve valid access_token automatically to KiteMarketDataProvider & KiteTickerManager
7. Provide safe status metadata without exposing any secrets
"""

import logging
import urllib.parse
from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from zoneinfo import ZoneInfo

from market.models import KiteCredential
from market.services.trading_session import IST_TIMEZONE
from market.exceptions import AuthenticationError, InvalidPayloadError

logger = logging.getLogger(__name__)

KITE_LOGIN_BASE_URL = "https://kite.zerodha.com/connect/login"


class KiteCredentialService:
    """
    Central service for personal Kite Connect credential management and token lifecycle.
    """

    @classmethod
    def get_api_key(cls) -> str:
        return getattr(settings, "KITE_API_KEY", "") or ""

    @classmethod
    def get_api_secret(cls) -> str:
        return getattr(settings, "KITE_API_SECRET", "") or ""

    @classmethod
    def get_redirect_url(cls) -> str:
        return getattr(settings, "KITE_REDIRECT_URL", "http://127.0.0.1:8000/kite/callback/")

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_api_key() and cls.get_api_secret())

    @classmethod
    def generate_login_url(cls) -> str:
        """
        Generates the official Zerodha OAuth login URL.
        Redirects the user to Zerodha's login portal for credentials + 2FA TOTP.
        """
        api_key = cls.get_api_key()
        if not api_key:
            raise AuthenticationError("Kite API key is not configured. Set KITE_API_KEY in settings/.env.")

        redirect_url = cls.get_redirect_url()
        params = {
            "api_key": api_key,
            "v": "3",
        }
        if redirect_url:
            params["redirect_url"] = redirect_url

        login_url = f"{KITE_LOGIN_BASE_URL}?{urllib.parse.urlencode(params)}"
        logger.info(f"Generated Kite login URL: {login_url}")
        return login_url

    @classmethod
    def calculate_expiry(cls, auth_time: Optional[datetime] = None) -> datetime:
        """
        Calculates when the daily Kite access token expires.
        Zerodha tokens expire daily at approximately 06:00 AM IST.
        """
        if auth_time is None:
            auth_time = timezone.now()

        ist_dt = auth_time.astimezone(IST_TIMEZONE)
        expiry_date = ist_dt.date()

        # If authenticated after 06:00 IST today, it expires tomorrow at 06:00 IST
        if ist_dt.time() >= time(6, 0):
            expiry_date = expiry_date + timedelta(days=1)

        expiry_ist = datetime.combine(expiry_date, time(6, 0), tzinfo=IST_TIMEZONE)
        return expiry_ist

    @classmethod
    def exchange_request_token(
        cls,
        request_token: str,
        account_id: str = "default",
        kite_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Exchanges request_token for access_token using Zerodha API secret.
        Persists the encrypted token in KiteCredential.
        """
        if not request_token or not request_token.strip():
            raise InvalidPayloadError("Missing or empty request_token.")

        api_key = cls.get_api_key()
        api_secret = cls.get_api_secret()

        if not api_key or not api_secret:
            raise AuthenticationError("Kite API key or API secret missing from settings/.env.")

        logger.info(f"Exchanging request_token for account '{account_id}'...")

        try:
            if kite_client is None:
                from kiteconnect import KiteConnect
                kite_client = KiteConnect(api_key=api_key)

            # Generate session via KiteConnect
            session_data = kite_client.generate_session(request_token.strip(), api_secret=api_secret)

            access_token = session_data.get("access_token")
            if not access_token:
                raise AuthenticationError("KiteConnect did not return an access_token in session payload.")

            user_id = session_data.get("user_id") or session_data.get("client_id")
            user_name = session_data.get("user_name")
            public_token = session_data.get("public_token", "")

            # Persist encrypted credential
            cred, _ = KiteCredential.objects.get_or_create(account_id=account_id)
            cred.user_id = user_id
            cred.user_name = user_name
            cred.public_token = public_token
            cred.request_token = request_token[:10] + "..."  # Truncate for audit without saving full raw token
            cred.set_access_token(access_token)
            cred.status = "CONNECTED"
            cred.authenticated_at = timezone.now()
            cred.expires_at = cls.calculate_expiry(cred.authenticated_at)
            cred.last_error = None
            cred.save()

            logger.info(f"Kite session successfully established for user '{user_id}'. Expires at {cred.expires_at}.")

            return {
                "success": True,
                "user_id": user_id,
                "user_name": user_name,
                "authenticated_at": cred.authenticated_at.isoformat(),
                "expires_at": cred.expires_at.isoformat(),
                "status": "CONNECTED",
            }

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Failed to exchange Kite request_token: {err_msg}")
            # Update credential status to ERROR
            cred, _ = KiteCredential.objects.get_or_create(account_id=account_id)
            cred.status = "ERROR"
            cred.last_error = err_msg
            cred.save()
            raise AuthenticationError(f"Kite token exchange failed: {err_msg}")

    @classmethod
    def get_valid_access_token(cls, account_id: str = "default") -> Optional[str]:
        """
        Retrieves the active, unexpired access_token.
        Automatically checks database and checks expiry against 06:00 IST cutoff.
        Falls back to KITE_ACCESS_TOKEN from environment if no DB token exists.
        """
        cred = KiteCredential.objects.filter(account_id=account_id).first()
        now = timezone.now()

        if cred and cred.encrypted_access_token:
            # Check expiry
            if cred.expires_at and now >= cred.expires_at:
                if cred.status != "EXPIRED":
                    cred.status = "EXPIRED"
                    cred.save()
                    logger.warning(f"Kite access token for '{account_id}' has expired.")
                return None

            token = cred.get_access_token()
            if token:
                return token

        # Fallback to env setting if configured
        env_token = getattr(settings, "KITE_ACCESS_TOKEN", "") or ""
        if env_token:
            return env_token

        return None

    @classmethod
    def get_safe_status(cls, account_id: str = "default") -> Dict[str, Any]:
        """
        Returns a non-sensitive status dictionary for frontend consumption.
        Never returns secrets or access tokens!
        """
        configured = cls.is_configured()
        cred = KiteCredential.objects.filter(account_id=account_id).first()
        now = timezone.now()

        if not configured:
            status = "NOT_CONFIGURED"
            is_authenticated = False
        elif not cred or not cred.encrypted_access_token:
            # Check if env token exists
            if getattr(settings, "KITE_ACCESS_TOKEN", ""):
                status = "CONNECTED"
                is_authenticated = True
            else:
                status = "AUTHENTICATION_REQUIRED"
                is_authenticated = False
        elif cred.expires_at and now >= cred.expires_at:
            status = "EXPIRED"
            is_authenticated = False
        else:
            status = cred.status
            is_authenticated = (status == "CONNECTED")

        login_url = None
        if configured and status in ("AUTHENTICATION_REQUIRED", "EXPIRED", "ERROR", "NOT_CONFIGURED"):
            try:
                login_url = cls.generate_login_url()
            except Exception:
                login_url = None

        return {
            "configured": configured,
            "authenticated": is_authenticated,
            "status": status,
            "user_id": cred.user_id if cred else None,
            "user_name": cred.user_name if cred else None,
            "authenticated_at": cred.authenticated_at.isoformat() if (cred and cred.authenticated_at) else None,
            "expires_at": cred.expires_at.isoformat() if (cred and cred.expires_at) else None,
            "last_error": cred.last_error if cred else None,
            "login_url": login_url,
            "provider": "kite",
        }

    @classmethod
    def disconnect(cls, account_id: str = "default") -> bool:
        """
        Invalidates the stored access token and marks status AUTHENTICATION_REQUIRED.
        """
        cred = KiteCredential.objects.filter(account_id=account_id).first()
        if cred:
            cred.set_access_token("")
            cred.status = "AUTHENTICATION_REQUIRED"
            cred.last_error = "User disconnected session manually."
            cred.save()
            logger.info(f"Kite session for '{account_id}' disconnected.")
            return True
        return False
