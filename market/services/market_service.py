import logging
from typing import Dict, Any
from django.utils import timezone
from market.models import Company, Instrument, MarketSnapshot
from market.providers.yfinance import YFinanceMarketProvider
from market.normalizers.yfinance import YFinanceNormalizer
from market.providers.base import MarketQuote

logger = logging.getLogger(__name__)

class MarketService:
    """
    Coordination service that interfaces with external providers, normalizes raw
    responses, and manages persistence to Company, Instrument, and MarketSnapshot tables.
    """
    
    def __init__(self, provider=None, normalizer=None):
        self.provider = provider or YFinanceMarketProvider()
        self.normalizer = normalizer or YFinanceNormalizer()
        
        # Sector and metadata mapping for common Indian stocks
        self._company_metadata = {
            "RELIANCE": {"name": "Reliance Industries Limited", "sector": "Energy", "industry": "Oil & Gas", "website": "https://www.ril.com"},
            "TCS": {"name": "Tata Consultancy Services Limited", "sector": "Technology", "industry": "IT Services", "website": "https://www.tcs.com"},
            "INFY": {"name": "Infosys Limited", "sector": "Technology", "industry": "IT Services", "website": "https://www.infosys.com"},
            "HDFCBANK": {"name": "HDFC Bank Limited", "sector": "Financial Services", "industry": "Private Banking", "website": "https://www.hdfcbank.com"},
            "ICICIBANK": {"name": "ICICI Bank Limited", "sector": "Financial Services", "industry": "Private Banking", "website": "https://www.icicibank.com"},
            "SBIN": {"name": "State Bank of India", "sector": "Financial Services", "industry": "Public Banking", "website": "https://www.sbi.co.in"},
            "BHARTIENTL": {"name": "Bharti Airtel Limited", "sector": "Telecommunications", "industry": "Telecom Services", "website": "https://www.airtel.in"}
        }

    def fetch_and_save_quote(self, symbol: str) -> MarketQuote:
        """
        Executes provider fetch, normalizes raw response to canonical schema,
        upserts Company & Instrument database records, records a new MarketSnapshot,
        and returns the canonical MarketQuote object.
        Enforces idempotency to prevent duplicate snapshot records.
        """
        logger.info(f"Fetching market quote for symbol: {symbol}")
        
        # 1. Fetch raw data from external source
        raw_data = self.provider.get_quote(symbol)
        
        # 2. Normalize to canonical schema
        canonical_quote = self.normalizer.normalize(raw_data)
        
        # 3. Resolve metadata and create/update Company
        clean_symbol = canonical_quote.symbol
        meta = self._company_metadata.get(clean_symbol, {
            "name": f"{clean_symbol} Limited",
            "sector": "Unknown",
            "industry": "Unknown",
            "website": None
        })
        
        company, _ = Company.objects.update_or_create(
            short_name=clean_symbol,
            defaults={
                "name": meta["name"],
                "sector": meta["sector"],
                "industry": meta["industry"],
                "website": meta["website"],
                "is_active": True
            }
        )
        
        # 4. Resolve and create/update Instrument
        instrument, _ = Instrument.objects.update_or_create(
            company=company,
            symbol=clean_symbol,
            exchange=canonical_quote.exchange,
            defaults={
                "instrument_type": "EQUITY",
                "currency": "INR",
                "is_active": True
            }
        )
        
        # 5. Check for idempotency: avoid duplicate snapshots for the same instrument and timestamp
        snapshot_exists = MarketSnapshot.objects.filter(
            instrument=instrument,
            timestamp=canonical_quote.timestamp
        ).exists()
        
        if not snapshot_exists:
            MarketSnapshot.objects.create(
                instrument=instrument,
                timestamp=canonical_quote.timestamp,
                open=canonical_quote.open_price,
                high=canonical_quote.high,
                low=canonical_quote.low,
                close=canonical_quote.close,
                volume=canonical_quote.volume,
                previous_close=canonical_quote.previous_close,
                change=canonical_quote.change,
                change_percent=canonical_quote.change_percent,
                source="YFinanceMarketProvider",
                source_timestamp=canonical_quote.timestamp
            )
            logger.info(f"Successfully recorded new market snapshot for {instrument} at price {canonical_quote.price}")
        else:
            logger.info(f"Snapshot already exists for {instrument} at timestamp {canonical_quote.timestamp}. Skipped creation to maintain idempotency.")
            
        return canonical_quote
