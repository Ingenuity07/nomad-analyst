from celery import shared_task
import logging
from market.models import Instrument
from market.services.market_service import MarketService

logger = logging.getLogger(__name__)

@shared_task
def update_instrument_quotes():
    """
    Celery task that iterates through all active stock instruments and fetches
    the latest price snapshot to record in the database.
    """
    logger.info("Starting periodic update of stock instrument quotes...")
    instruments = Instrument.objects.filter(is_active=True)
    service = MarketService()
    
    success_count = 0
    fail_count = 0
    
    for inst in instruments:
        try:
            service.fetch_and_save_quote(inst.symbol)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to update quote for symbol {inst.symbol}: {e}")
            fail_count += 1
            
    logger.info(f"Completed periodic quote update. Success: {success_count}, Failures: {fail_count}")
    return {"status": "Complete", "success": success_count, "failed": fail_count}


@shared_task
def refresh_market_context():
    """
    Celery task that fetches quotes and historical bars for indices and global cues,
    calculates indicator features, and saves a MarketContextSnapshot.
    """
    from django.utils import timezone as django_timezone
    from datetime import timedelta
    from market.services.market_service import MarketService
    from market.services.feature_engine import TechnicalFeatureEngine
    from market.services.context_service import MarketContextService
    
    logger.info("Starting refresh of market context indices and global cues...")
    
    indices = ["^NSEI", "^NSEBANK"]
    global_cues = ["^GSPC", "^IXIC", "^DJI", "^VIX", "USDINR=X", "CL=F", "GC=F", "^TNX"]
    
    market_service = MarketService()
    feature_engine = TechnicalFeatureEngine()
    context_service = MarketContextService()
    
    # 1. Fetch latest quotes & historical bars
    for symbol in (indices + global_cues):
        try:
            # Save latest snapshot
            market_service.fetch_and_save_quote(symbol)
            # Fetch last 90 days of bars (warmup standard)
            end_date = django_timezone.now()
            start_date = end_date - timedelta(days=90)
            market_service.fetch_and_save_historical_ohlcv(symbol, timeframe="1d", start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.error(f"refresh_market_context: failed to fetch data for symbol {symbol}: {e}")

    # 2. Run TechnicalFeatureEngine over indices
    for index in indices:
        try:
            inst = Instrument.objects.filter(symbol=index, is_active=True).first()
            if inst:
                feature_engine.calculate_and_save_features(inst)
        except Exception as e:
            logger.error(f"refresh_market_context: failed to calculate features for index {index}: {e}")

    # 3. Build and save MarketContextSnapshot
    try:
        context = context_service.get_market_context()
        snapshot = context_service.save_market_context_snapshot(context)
        logger.info(f"Successfully saved MarketContextSnapshot for as_of: {snapshot.as_of}")
        return {"status": "Success", "as_of": snapshot.as_of.isoformat()}
    except Exception as e:
        logger.error(f"refresh_market_context: failed to save context snapshot: {e}")
        return {"status": "Failed", "error": str(e)}


@shared_task
def run_daily_opportunity_scan():
    """
    Celery task that runs opportunity scanning and ranking daily for all active universes
    under both DELIVERY_SWING and LONG_TERM horizons.
    """
    from market.models import Universe
    from market.services.discovery_service import OpportunityDiscoveryService
    
    logger.info("Starting daily stock opportunity discovery scan...")
    service = OpportunityDiscoveryService()
    
    active_universes = list(Universe.objects.filter(is_active=True))
    if not active_universes:
        # Fallback to scanning NIFTY50 as default
        logger.warning("No active Universe objects found in database. Scanning default NIFTY50.")
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            try:
                snapshots = service.scan_universe("NIFTY50", horizon)
                logger.info(f"Successfully generated {len(snapshots)} opportunity snapshots for NIFTY50 under horizon {horizon}")
            except Exception as e:
                logger.error(f"Failed to scan default NIFTY50 for horizon {horizon}: {e}")
        return {"status": "Complete", "universes_scanned": ["NIFTY50"]}

    scanned_names = []
    for univ in active_universes:
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            try:
                snapshots = service.scan_universe(univ.name, horizon)
                logger.info(f"Successfully generated {len(snapshots)} opportunity snapshots for {univ.name} under horizon {horizon}")
            except Exception as e:
                logger.error(f"Failed to scan universe {univ.name} for horizon {horizon}: {e}")
        scanned_names.append(univ.name)
        
    return {"status": "Complete", "universes_scanned": scanned_names}


@shared_task
def run_daily_recommendation_scan():
    """
    Celery task that runs the deterministic signal engine over all active universes
    and persists StockRecommendation records for DELIVERY_SWING and LONG_TERM horizons.

    Runs daily after run_daily_opportunity_scan.
    Only generates deterministic records — no LLM calls are made here.
    """
    from market.models import Universe
    from market.services.recommendation_service import RecommendationService

    logger.info("Starting daily recommendation scan...")
    service = RecommendationService()

    active_universes = list(Universe.objects.filter(is_active=True))
    if not active_universes:
        # Fallback to NIFTY50
        logger.warning("No active Universe objects found. Running default NIFTY50 scan.")
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            try:
                result = service.scan_and_recommend("NIFTY50", horizon)
                logger.info(f"Recommendation scan complete: {result}")
            except Exception as e:
                logger.error(f"run_daily_recommendation_scan: NIFTY50 [{horizon}] failed: {e}")
        return {"status": "Complete", "universes_scanned": ["NIFTY50"]}

    scanned = []
    for univ in active_universes:
        for horizon in ("DELIVERY_SWING", "LONG_TERM"):
            try:
                result = service.scan_and_recommend(univ.name, horizon)
                logger.info(
                    f"Recommendation scan: {univ.name} [{horizon}] → "
                    f"generated={result.get('generated', 0)}, errors={result.get('errors', 0)}"
                )
            except Exception as e:
                logger.error(f"run_daily_recommendation_scan: {univ.name} [{horizon}] failed: {e}")
        scanned.append(univ.name)

    # Expire stale ACTIVE recommendations
    try:
        expired = service.expire_old_active_recommendations(max_age_days=10)
        if expired:
            logger.info(f"Expired {expired} stale ACTIVE recommendations.")
    except Exception as e:
        logger.warning(f"Could not expire stale recommendations: {e}")

    return {"status": "Complete", "universes_scanned": scanned}


@shared_task
def run_intraday_incremental_update():
    """
    Celery task — runs every 5 minutes during NSE market hours.

    Fetches the most recent 5m bars for all EQUITY instruments in active
    universes. Skips run entirely if the market is currently closed.

    Design rules:
      - Idempotent: safe to call multiple times; no duplicate candles created.
      - Market-hours-only: does NOT fetch outside NSE session.
      - Rate-limit aware: 1.5s delay between instruments.
      - Bounded: fetches only the last INCREMENTAL_LOOKBACK_DAYS window.
    """
    from datetime import datetime, timezone
    from market.models import Universe, UniverseMembership, Instrument
    from market.services.market_session import IndianMarketSession
    from market.services.intraday_service import IntradayMarketDataService
    import time as _time

    now_utc = datetime.now(timezone.utc)
    session = IndianMarketSession()

    if not session.is_market_open(now_utc):
        logger.info(
            "run_intraday_incremental_update: market is closed. Skipping."
        )
        return {"status": "SKIPPED", "reason": "market_closed", "at": now_utc.isoformat()}

    logger.info("run_intraday_incremental_update: market is open — starting incremental fetch.")

    # Collect all active equity instruments from active universes
    active_symbols: set[str] = set()
    for univ in Universe.objects.filter(is_active=True):
        members = UniverseMembership.objects.filter(
            universe=univ, is_active=True
        ).select_related("instrument")
        for m in members:
            if m.instrument.instrument_type == "EQUITY" and m.instrument.is_active:
                active_symbols.add(m.instrument.symbol)

    if not active_symbols:
        logger.warning("run_intraday_incremental_update: no active equity instruments found.")
        return {"status": "NO_INSTRUMENTS"}

    intraday_svc = IntradayMarketDataService()
    results = {"success": 0, "failed": 0, "new_bars": 0}

    for symbol in sorted(active_symbols):
        try:
            result = intraday_svc.incremental_update(symbol, "5m")
            results["new_bars"] += result.get("new_bars", 0)
            results["success"] += 1
        except Exception as e:
            logger.error(
                f"run_intraday_incremental_update: failed for {symbol}: {e}"
            )
            results["failed"] += 1
        _time.sleep(1.5)

    logger.info(
        f"run_intraday_incremental_update: complete. "
        f"success={results['success']}, failed={results['failed']}, "
        f"new_bars={results['new_bars']}"
    )
    return {"status": "Complete", **results}


@shared_task
def run_intraday_backfill_task(symbol: str = None, timeframe: str = "5m", days_back: int = 30):
    """
    On-demand intraday historical backfill task.

    Can be called for a specific symbol or for all active equity instruments
    in active universes.

    Parameters:
      symbol    — if provided, backfill only this symbol; else backfill all active equities.
      timeframe — one of '5m', '15m', '1h' (default '5m').
      days_back — number of calendar days to backfill (provider limits apply).

    This task is NOT scheduled automatically. It is triggered manually:
      celery.send_task('market.tasks.run_intraday_backfill_task',
                       kwargs={'symbol': 'RELIANCE', 'timeframe': '5m', 'days_back': 30})
    """
    from market.models import Universe, UniverseMembership
    from market.services.intraday_service import IntradayMarketDataService
    import time as _time

    svc = IntradayMarketDataService()

    if symbol:
        symbols = [symbol.strip().upper()]
    else:
        active_symbols: set[str] = set()
        for univ in Universe.objects.filter(is_active=True):
            for m in UniverseMembership.objects.filter(
                universe=univ, is_active=True
            ).select_related("instrument"):
                if m.instrument.instrument_type == "EQUITY" and m.instrument.is_active:
                    active_symbols.add(m.instrument.symbol)
        symbols = sorted(active_symbols)

    logger.info(
        f"run_intraday_backfill_task: backfilling {len(symbols)} symbol(s) "
        f"[{timeframe}, {days_back}d]"
    )

    results = {"success": 0, "failed": 0, "total_new_bars": 0}
    for sym in symbols:
        try:
            result = svc.backfill(sym, timeframe, days_back)
            results["success"] += 1
            results["total_new_bars"] += result.get("new_bars_ingested", 0)
        except Exception as e:
            logger.error(f"run_intraday_backfill_task: failed for {sym}: {e}")
            results["failed"] += 1
        _time.sleep(2.0)

    logger.info(f"run_intraday_backfill_task: done. {results}")
    return {"status": "Complete", **results}


# ─── Module 10: Intraday Strategy Tasks ──────────────────────────────────────

@shared_task
def run_intraday_strategy_scan():
    """
    Module 10 — Intraday strategy signal scan.

    Runs every 5 minutes during market hours (gated by IndianMarketSession).
    For each active EQUITY instrument, calls IntradaySignalEngine to generate
    an intraday recommendation draft. If signal is BUY or SELL, persists it
    via RecommendationService.

    Self-gates on market hours — safe to schedule unconditionally.
    """
    import time as _time
    from django.utils import timezone
    from market.services.market_session import IndianMarketSession
    from market.services.intraday_signal_engine import IntradaySignalEngine
    from market.services.recommendation_service import RecommendationService
    from market.signal_enums import SignalDirection
    from market.models import Instrument
    from market.intraday_strategy_config import DEFAULT_INTRADAY_TIMEFRAME

    if not IndianMarketSession.is_market_open():
        logger.info("run_intraday_strategy_scan: market is closed. Skipping.")
        return {"status": "SKIPPED", "reason": "market_closed"}

    engine = IntradaySignalEngine()
    svc = RecommendationService()
    now = timezone.now()
    timeframe = DEFAULT_INTRADAY_TIMEFRAME

    instruments = list(
        Instrument.objects.filter(is_active=True, instrument_type="EQUITY")
        .select_related("company")[:200]
    )

    if not instruments:
        logger.warning("run_intraday_strategy_scan: no active equity instruments found.")
        return {"status": "NO_INSTRUMENTS"}

    results = {"total": len(instruments), "actionable": 0, "skipped": 0, "failed": 0, "skip_reasons": {}}

    for inst in instruments:
        try:
            draft = engine.generate_recommendation(inst, timeframe=timeframe, as_of=now)

            if draft.signal in (SignalDirection.BUY.value, SignalDirection.SELL.value):
                # Persist actionable recommendation directly with all intraday fields intact
                rec = svc.save_draft(draft, instrument=inst)
                results["actionable"] += 1
            else:
                results["skipped"] += 1
                reason = draft.invalidation_reason or draft.signal or "NO_ACTION"
                results["skip_reasons"][reason] = results["skip_reasons"].get(reason, 0) + 1

        except Exception as e:
            logger.error(f"run_intraday_strategy_scan: failed for {inst.symbol}: {e}")
            results["failed"] += 1

        _time.sleep(0.1)  # light throttle to avoid burst

    logger.info(f"run_intraday_strategy_scan: complete. {results}")
    return {"status": "Complete", **results}


@shared_task
def expire_intraday_session_recommendations():
    """
    Module 10 — Expire stale intraday recommendations at/after market close.

    Should run at 15:35 IST daily (after market close at 15:30).
    Marks all ACTIVE intraday recommendations whose expires_at <= now as EXPIRED.
    No records are deleted — historical trail is preserved.
    """
    from django.utils import timezone
    from market.services.intraday_lifecycle import expire_intraday_session_recommendations as _expire

    now = timezone.now()
    expired = _expire(now)
    logger.info(f"expire_intraday_session_recommendations: marked {expired} recs as EXPIRED.")
    return {"status": "Complete", "expired_count": expired}


# ─── Module 11 — Recommendation Outcome Tracking ─────────────────────────────

@shared_task
def evaluate_recommendation_outcomes():
    """
    Module 11 — Live outcome evaluation for active recommendations.

    Evaluates all ACTIVE StockRecommendations against newly available market
    bar data. Runs every 5 minutes during market hours.

    Processing is idempotent: running twice on the same bar data produces
    the same outcome record (no duplicates).

    CRITICAL: This task does NOT run full historical backtests. For backtesting,
    use BacktestRunner.run() explicitly.
    """
    from django.utils import timezone
    from market.services.market_session import IndianMarketSession
    from market.services.outcome_service import RecommendationOutcomeService

    now = timezone.now()

    # Self-gate: only run during market hours (extended slightly for evaluation)
    session = IndianMarketSession()
    if not session.is_market_open(now):
        logger.info("evaluate_recommendation_outcomes: market closed, skipping.")
        return {"status": "SKIPPED", "reason": "market_closed"}

    svc = RecommendationOutcomeService()
    summary = svc.evaluate_active_recommendations(as_of=now)

    logger.info(f"evaluate_recommendation_outcomes: complete. {summary}")
    return {"status": "Complete", **summary}
