"""
Nomad Analyst — F&O Presentation Layer Views
Reference: Phase FNO-1 & FNO-1A Implementation
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
import os
import zoneinfo

from django.core.cache import cache
from django.db import connection
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from fno.models import OptionQuoteSnapshot, OptionOHLCVBar, PaperTradeLedger
from fno.serializers import OptionQuoteSnapshotSerializer, PaperTradeLedgerSerializer
from fno.services.option_registry import CONFIG_NIFTY, OptionInstrumentRegistry
from market.models import MarketContextSnapshot, MarketSnapshot

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Process-level singleton cache for option instrument registry
_REGISTRY_INSTANCE = None


def get_cached_option_registry() -> OptionInstrumentRegistry:
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = OptionInstrumentRegistry()
        try:
            _REGISTRY_INSTANCE.load_master()
        except Exception:
            pass
    return _REGISTRY_INSTANCE


def check_ticker_daemon_running() -> tuple[bool, int | None]:
    """Inspects PID lockfile to verify whether run_intraday_ticker daemon is active."""
    pid_file_path = "/tmp/nomad_intraday_ticker.pid"
    if not os.path.exists(pid_file_path):
        return False, None
    try:
        with open(pid_file_path, "r") as f:
            pid_str = f.read().strip()
        if not pid_str:
            return False, None
        pid = int(pid_str)
        os.kill(pid, 0)
        return True, pid
    except (OSError, ValueError):
        return False, None


def is_nse_market_open(now_ist: datetime) -> bool:
    """Returns True if current IST time falls within regular NSE trading hours (09:15–15:30, Mon–Fri)."""
    # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
    if now_ist.weekday() >= 5:
        return False
    market_open = time(9, 15)
    market_close = time(15, 30)
    current_time = now_ist.time()
    return market_open <= current_time <= market_close


class FnoOverviewAPIView(APIView):
    """
    GET /api/v1/fno/overview/
    Returns real-time NIFTY spot context, ATM strike, active option quotes ladder,
    and ingestion telemetry.
    """
    def get(self, request):
        now_utc = django_tz.now()
        now_ist = now_utc.astimezone(IST)
        market_open = is_nse_market_open(now_ist)
        ticker_running, ticker_pid = check_ticker_daemon_running()

        # 1. Underlying NIFTY Context
        market_ctx = MarketContextSnapshot.objects.order_by('-as_of').first()
        nifty_snap = MarketSnapshot.objects.filter(instrument__symbol='^NSEI').order_by('-timestamp').first()

        spot_price = None
        if nifty_snap and nifty_snap.close is not None:
            spot_price = float(nifty_snap.close)
        elif market_ctx and isinstance(market_ctx.index_regimes, dict):
            nifty_regime = market_ctx.index_regimes.get('NIFTY', {})
            if isinstance(nifty_regime, dict) and 'close' in nifty_regime:
                try:
                    spot_price = float(nifty_regime['close'])
                except (ValueError, TypeError):
                    pass

        market_direction = market_ctx.market_direction if market_ctx else "NEUTRAL"
        market_regime = market_ctx.market_regime if market_ctx else "UNKNOWN"

        # 2. Authoritative ATM Strike Calculation using CONFIG_NIFTY and ROUND_HALF_UP
        atm_strike = None
        if spot_price is not None:
            step = CONFIG_NIFTY.strike_step
            spot_dec = Decimal(str(spot_price))
            multiple = (spot_dec / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            atm_strike = int(multiple * step)

        # 3. Active Option Quote Snapshots (Latest per token)
        if connection.vendor == 'postgresql':
            quotes_qs = list(
                OptionQuoteSnapshot.objects
                .order_by('instrument_token', '-received_wall_clock_utc')
                .distinct('instrument_token')[:60]
            )
        else:
            tokens = OptionQuoteSnapshot.objects.values_list('instrument_token', flat=True).distinct()[:60]
            quotes_qs = [
                OptionQuoteSnapshot.objects.filter(instrument_token=t).order_by('-received_wall_clock_utc').first()
                for t in tokens
            ]
            quotes_qs = [q for q in quotes_qs if q is not None]

        # Enrich quotes with registry metadata (tradingsymbol, strike, option_type, expiry)
        registry = get_cached_option_registry()
        for q in quotes_qs:
            meta = registry.get_contract_by_token(q.instrument_token)
            if meta:
                q.tradingsymbol = meta.tradingsymbol
                q.strike_price = meta.strike
                q.option_type = meta.instrument_type
                q.expiry_date = meta.expiry
            else:
                q.strike_price = None
                q.option_type = None
                q.expiry_date = None

        # Sort quotes ladder by strike_price and option_type around ATM
        quotes_qs.sort(
            key=lambda x: (
                x.strike_price if x.strike_price is not None else Decimal("0"),
                x.option_type or "",
                x.tradingsymbol
            )
        )

        quotes_data = OptionQuoteSnapshotSerializer(quotes_qs, many=True).data

        # 4. Ingestion Telemetry & Feed Status
        latest_quote = OptionQuoteSnapshot.objects.order_by('-received_wall_clock_utc').first()
        total_quotes_count = OptionQuoteSnapshot.objects.count()
        total_bars_count = OptionOHLCVBar.objects.count()

        last_tick_age = None
        if latest_quote and latest_quote.received_wall_clock_utc:
            age = (now_utc - latest_quote.received_wall_clock_utc).total_seconds()
            last_tick_age = round(age, 1)

        if not ticker_running:
            feed_status = "DISCONNECTED"
        elif not market_open:
            feed_status = "STANDBY_MARKET_CLOSED"
        else:
            if last_tick_age is not None and last_tick_age <= 30.0:
                feed_status = "ACTIVE"
            elif last_tick_age is not None and last_tick_age <= 120.0:
                feed_status = "DEGRADED"
            else:
                feed_status = "DISCONNECTED"

        return Response({
            "underlying": {
                "symbol": "^NSEI",
                "name": "NIFTY 50",
                "spot_price": spot_price,
                "atm_strike": atm_strike,
                "direction": market_direction,
                "market_direction": market_direction,
                "regime": market_regime,
                "market_regime": market_regime,
                "as_of": market_ctx.as_of.isoformat() if market_ctx else None,
            },
            "feed": {
                "status": feed_status,
                "market_session": "OPEN" if market_open else "CLOSED",
                "ticker_running": ticker_running,
                "ticker_pid": ticker_pid,
                "quote_age_seconds": last_tick_age,
                "last_received_age_seconds": last_tick_age,
                "latest_exchange_timestamp": latest_quote.exchange_timestamp_utc.isoformat() if latest_quote and latest_quote.exchange_timestamp_utc else None,
                "latest_received_wall_clock": latest_quote.received_wall_clock_utc.isoformat() if latest_quote else None,
                "latest_quote_timestamp": latest_quote.received_wall_clock_utc.isoformat() if latest_quote else None,
                "active_contracts_tracked": len(quotes_data),
                "active_tokens_count": len(quotes_data),
                "total_quotes_today": total_quotes_count,
                "total_bars_today": total_bars_count,
            },
            "quotes": quotes_data,
            "timestamp": now_ist.isoformat(),
        }, status=status.HTTP_200_OK)


class FnoStrategyAPIView(APIView):
    """
    GET /api/v1/fno/strategy/
    Returns STRAT-ORB-15M strategy status, opening range bounds, formation progress,
    and recent evaluation/decision logs sourced strictly from authoritative runtime telemetry.
    """
    def get(self, request):
        now_utc = django_tz.now()
        now_ist = now_utc.astimezone(IST)
        session_date = now_ist.date()

        # 1. Inspect Authoritative Runtime Telemetry from Redis Cache
        cache_key = f"fno_strategy_health:{session_date}:STRAT-ORB-15M"
        cached_health = cache.get(cache_key)

        # 2. Check historical NIFTY spot bars for informational context
        start_ist = datetime.combine(session_date, time(9, 15), tzinfo=IST)
        end_ist = datetime.combine(session_date, time(9, 30), tzinfo=IST)

        spot_bars = MarketSnapshot.objects.filter(
            instrument__symbol="^NSEI",
            timestamp__gte=start_ist,
            timestamp__lt=end_ist,
        ).order_by("timestamp")
        available_bars = spot_bars.count()

        if cached_health:
            runtime_available = True
            is_enabled = cached_health.get("is_enabled", False)
            range_established = cached_health.get("opening_range_established", False)
            range_high = cached_health.get("opening_range_high")
            range_low = cached_health.get("opening_range_low")
            range_width = round(range_high - range_low, 2) if (range_high is not None and range_low is not None) else None

            if range_established:
                range_status = "LOCKED"
                strategy_status = "ACTIVE" if is_enabled else "PAUSED"
            elif now_ist.time() < time(9, 15):
                range_status = "PENDING_OPEN"
                strategy_status = "PENDING_RANGE"
            elif now_ist.time() < time(9, 30):
                range_status = "FORMING"
                strategy_status = "FORMING_RANGE"
            else:
                range_status = "FAIL_CLOSED"
                strategy_status = "INCOMPLETE_RANGE"

            evaluations_count = cached_health.get("evaluations_count", 0)
            eligible_evaluations = cached_health.get("eligible_evaluations", 0)
            signals_count = cached_health.get("signals_count", 0)
            rejection_breakdown = cached_health.get("rejection_breakdown", {})
            rejections_count = cached_health.get("rejections_count", sum(rejection_breakdown.values()))
            last_evaluation_time = cached_health.get("last_evaluation_time")
        else:
            # Runtime telemetry not published (daemon offline or session not yet evaluated)
            runtime_available = False
            strategy_status = "UNAVAILABLE"
            range_established = False
            range_high = None
            range_low = None
            range_width = None
            range_status = "UNAVAILABLE"
            evaluations_count = None
            eligible_evaluations = None
            signals_count = 0
            rejection_breakdown = {}
            rejections_count = 0
            last_evaluation_time = None

        # 3. Recent Strategy Trades / Decisions from Ledger
        recent_ledger_entries = (
            PaperTradeLedger.objects
            .filter(strategy_id="STRAT-ORB-15M")
            .order_by("-entry_timestamp")[:30]
        )
        recent_signals = PaperTradeLedgerSerializer(recent_ledger_entries, many=True).data

        return Response({
            "strategy": {
                "strategy_id": "STRAT-ORB-15M",
                "name": "NIFTY 15m Opening Range Breakout",
                "version": cached_health.get("strategy_version", "1.0.0") if cached_health else "1.0.0",
                "status": strategy_status,
                "runtime_telemetry_available": runtime_available,
                "session_date": str(session_date),
                "last_evaluation_time": last_evaluation_time,
            },
            "opening_range": {
                "expected_bars": 15,
                "available_bars": available_bars,
                "runtime_established": range_established,
                "range_high": range_high,
                "range_low": range_low,
                "range_width": range_width,
                "status": range_status,
                "time_window": "09:15–09:30 IST",
            },
            "audit_trail": {
                "evaluations_count": evaluations_count,
                "eligible_evaluations": eligible_evaluations,
                "signals_count": signals_count,
                "rejections_count": rejections_count,
                "rejection_summary": rejection_breakdown,
                "recent_signals": recent_signals,
                "total_signals_today": signals_count,
            },
            "timestamp": now_ist.isoformat(),
        }, status=status.HTTP_200_OK)


class FnoTradesAPIView(APIView):
    """
    GET /api/v1/fno/trades/
    Returns active open paper positions, completed session trades, fill details,
    statutory frictions, and session performance statistics.
    """
    def get(self, request):
        now_utc = django_tz.now()
        now_ist = now_utc.astimezone(IST)

        open_trades_qs = PaperTradeLedger.objects.filter(
            status__in=["OPEN", "PARTIALLY_FILLED", "PENDING_ENTRY", "PENDING_LIQUIDITY"]
        ).order_by("-entry_timestamp")

        closed_trades_qs = PaperTradeLedger.objects.filter(
            status="CLOSED"
        ).order_by("-exit_timestamp")

        rejected_trades_qs = PaperTradeLedger.objects.filter(
            status="REJECTED"
        ).order_by("-entry_timestamp")[:50]

        total_ledger_count = PaperTradeLedger.objects.count()
        ledger_status = "POPULATED" if total_ledger_count > 0 else "EMPTY"

        # Calculate Session Performance
        closed_trades = list(closed_trades_qs)
        total_closed = len(closed_trades)
        wins = sum(1 for t in closed_trades if (t.net_pnl or Decimal("0.00")) > Decimal("0.00"))
        losses = sum(1 for t in closed_trades if (t.net_pnl or Decimal("0.00")) < Decimal("0.00"))
        win_rate = round((wins / total_closed) * 100.0, 1) if total_closed > 0 else 0.0

        gross_pnl = sum((t.gross_pnl or Decimal("0.00")) for t in closed_trades)
        net_pnl = sum((t.net_pnl or Decimal("0.00")) for t in closed_trades)
        total_frictions = sum((t.total_frictions or Decimal("0.00")) for t in closed_trades)

        return Response({
            "summary": {
                "ledger_status": ledger_status,
                "total_trades": total_closed,
                "open_positions_count": open_trades_qs.count(),
                "wins": wins,
                "losses": losses,
                "win_rate_pct": win_rate,
                "gross_pnl": str(round(gross_pnl, 2)),
                "net_pnl": str(round(net_pnl, 2)),
                "total_frictions": str(round(total_frictions, 2)),
                "is_paper_trading": True,
            },
            "open_positions": PaperTradeLedgerSerializer(open_trades_qs, many=True).data,
            "closed_trades": PaperTradeLedgerSerializer(closed_trades_qs, many=True).data,
            "rejections": PaperTradeLedgerSerializer(rejected_trades_qs, many=True).data,
            "timestamp": now_ist.isoformat(),
        }, status=status.HTTP_200_OK)


class FnoDiagnosticsAPIView(APIView):
    """
    GET /api/v1/fno/diagnostics/
    Returns 1m bar completeness metrics, quote snapshot health, feed latency,
    and process status.
    """
    def get(self, request):
        now_utc = django_tz.now()
        now_ist = now_utc.astimezone(IST)
        session_date = now_ist.date()
        ticker_running, ticker_pid = check_ticker_daemon_running()

        # Option Bars Aggregation Health (filtered strictly for 1-minute aggregation)
        today_bars = OptionOHLCVBar.objects.filter(
            timeframe="1m",
            timestamp__date=session_date
        )
        total_bars_count = today_bars.count()
        partial_bars_count = today_bars.filter(is_partial_bar=True).count()
        complete_bars_count = total_bars_count - partial_bars_count
        partial_ratio = round((partial_bars_count / total_bars_count) * 100.0, 2) if total_bars_count > 0 else 0.0

        # Option Quote Snapshots Health
        today_quotes = OptionQuoteSnapshot.objects.filter(
            received_wall_clock_utc__date=session_date
        )
        total_quotes_count = today_quotes.count()
        stale_quotes_count = today_quotes.filter(is_stale=True).count()
        eligible_quotes_count = today_quotes.filter(is_execution_eligible=True).count()

        latest_quote = OptionQuoteSnapshot.objects.order_by("-received_wall_clock_utc").first()
        feed_latency = None
        if latest_quote and latest_quote.received_wall_clock_utc and latest_quote.exchange_timestamp_utc:
            feed_latency = round(
                (latest_quote.received_wall_clock_utc - latest_quote.exchange_timestamp_utc).total_seconds(),
                3
            )

        # Component health
        db_healthy = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_healthy = False

        return Response({
            "session_date": str(session_date),
            "bars": {
                "total_today": total_bars_count,
                "complete_count": complete_bars_count,
                "partial_count": partial_bars_count,
                "partial_ratio_pct": partial_ratio,
                "quality_status": "EXCELLENT" if partial_ratio < 2.0 else "DEGRADED" if partial_ratio < 10.0 else "CRITICAL",
            },
            "quotes": {
                "total_today": total_quotes_count,
                "eligible_count": eligible_quotes_count,
                "stale_count": stale_quotes_count,
                "latest_feed_latency_seconds": feed_latency,
            },
            "components": {
                "postgresql": "HEALTHY" if db_healthy else "UNHEALTHY",
                "ticker_daemon": "RUNNING" if ticker_running else "STOPPED",
                "ticker_pid": ticker_pid,
                "fee_schedule": "NSE_CIRCULAR_73061_0.03553%",
                "paper_execution_mode": "STRICT_SIMULATED",
            },
            "timestamp": now_ist.isoformat(),
        }, status=status.HTTP_200_OK)

