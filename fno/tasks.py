"""
fno/tasks.py — Celery tasks for the F&O engine.
Includes post-market quote snapshot cleanup and retention enforcement.
"""

import logging
from celery import shared_task
from fno.services.option_quote_manager import OptionQuoteManager

logger = logging.getLogger(__name__)


@shared_task(name="fno.tasks.purge_expired_option_quotes")
def purge_expired_option_quotes(days: int = 5) -> dict:
    """
    Idempotently purges OptionQuoteSnapshot records older than `days` (default: 5).
    Safely bounds disk storage without impacting active trading sessions.
    """
    try:
        deleted_count = OptionQuoteManager.purge_expired_quotes(days=days)
        logger.info(
            f"purge_expired_option_quotes completed: deleted {deleted_count} expired records older than {days} days."
        )
        return {
            "status": "SUCCESS",
            "deleted_count": deleted_count,
            "retention_days": days,
        }
    except Exception as e:
        logger.error(f"Error purging expired option quotes: {e}", exc_info=True)
        return {
            "status": "ERROR",
            "error": str(e),
            "retention_days": days,
        }
