import time
from typing import Dict, Optional

class ProviderHealthMonitor:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ProviderHealthMonitor, cls).__new__(cls, *args, **kwargs)
            cls._instance.health_status = {}
            cls._instance.model_health_status = {}
        return cls._instance

    def report_failure(
        self,
        provider_name: str,
        model_name: Optional[str] = None,
        status_code: int = 500,
        blacklist_duration: int = 120,
    ):
        """
        Record a failure for the provider or a specific model.
        - If status_code indicates an account-wide issue (401, 403, 429), blacklist the entire provider.
        - If model_name is provided and it's a server/transient error (500, 502, 503, 504, 404),
          cooldown only that specific model to allow intra-provider failover.
        """
        now = time.time()
        is_provider_wide = status_code in (401, 403, 429) or not model_name

        if is_provider_wide:
            self.health_status[provider_name] = {
                "healthy": False,
                "status_code": status_code,
                "cooldown_until": now + blacklist_duration,
                "failed_at": now,
            }
        else:
            if not hasattr(self, "model_health_status"):
                self.model_health_status = {}
            self.model_health_status[f"{provider_name}:{model_name}"] = {
                "healthy": False,
                "status_code": status_code,
                "cooldown_until": now + blacklist_duration,
                "failed_at": now,
            }

    def report_success(self, provider_name: str, model_name: Optional[str] = None):
        """Mark a provider or specific model as healthy."""
        self.health_status[provider_name] = {
            "healthy": True,
            "cooldown_until": 0,
            "failed_at": 0,
        }
        if model_name:
            if not hasattr(self, "model_health_status"):
                self.model_health_status = {}
            self.model_health_status[f"{provider_name}:{model_name}"] = {
                "healthy": True,
                "cooldown_until": 0,
                "failed_at": 0,
            }

    def is_healthy(self, provider_name: str, model_name: Optional[str] = None) -> bool:
        """Verify if the provider and optional model are healthy or have passed their cooldown period."""
        now = time.time()

        # Check provider-level health
        status = self.health_status.get(provider_name)
        if status and not status.get("healthy"):
            if now > status.get("cooldown_until", 0):
                self.report_success(provider_name)
            else:
                return False

        # Check model-level health
        if model_name:
            if not hasattr(self, "model_health_status"):
                self.model_health_status = {}
            key = f"{provider_name}:{model_name}"
            m_status = self.model_health_status.get(key)
            if m_status and not m_status.get("healthy"):
                if now > m_status.get("cooldown_until", 0):
                    self.report_success(provider_name, model_name)
                    return True
                return False

        return True

    def reset(self, provider_name: str = None):
        """Reset health status for a specific provider or all providers."""
        if provider_name:
            self.health_status.pop(provider_name, None)
            if hasattr(self, "model_health_status"):
                self.model_health_status = {
                    k: v for k, v in self.model_health_status.items() if not k.startswith(f"{provider_name}:")
                }
        else:
            self.health_status.clear()
            if hasattr(self, "model_health_status"):
                self.model_health_status.clear()
