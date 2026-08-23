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
