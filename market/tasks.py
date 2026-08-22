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
