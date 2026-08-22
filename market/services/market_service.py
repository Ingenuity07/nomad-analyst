import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import re
from django.db import transaction
from market.models import Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature
from market.providers.yfinance import YFinanceMarketProvider
from market.normalizers.yfinance import YFinanceNormalizer
from market.providers.base import MarketQuote
from market.services.feature_engine import TechnicalFeatureEngine

logger = logging.getLogger(__name__)

class MarketService:
    """
    Coordination service that interfaces with external providers, normalizes raw
    responses, and manages persistence to Company, Instrument, and MarketSnapshot tables.
    Also handles historical OHLCV bar ingestion, data quality checks, and technical indicator calculations.
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

    def fetch_and_save_historical_ohlcv(self, symbol: str, timeframe: str = "1d", start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[OHLCVBar]:
        """
        Fetches historical data, normalizes, validates against strict quality checks,
        and saves bars to the OHLCVBar table in bulk to maintain idempotency.
        """
        logger.info(f"Fetching historical OHLCV for symbol: {symbol} [{timeframe}]")
        
        # 1. Fetch raw historical data
        raw_data = self.provider.get_historical_ohlcv(symbol, timeframe, start_date, end_date)
        
        if not raw_data or "chart" not in raw_data or not raw_data["chart"].get("result"):
            raise ValueError("Malformed historical payload: missing chart result.")
            
        result = raw_data["chart"]["result"][0]
        meta = result.get("meta")
        if not meta:
            raise ValueError("Malformed historical payload: missing metadata (meta).")
            
        # 2. Resolve Symbol and Exchange
        raw_symbol = meta.get("symbol")
        if not raw_symbol or not isinstance(raw_symbol, str):
            raise ValueError("Invalid symbol in historical metadata.")
        clean_symbol = raw_symbol.split('.')[0].strip()
        if not clean_symbol or not re.match(r"^[A-Za-z0-9_\-]+$", clean_symbol):
            raise ValueError(f"Invalid symbol characters: '{clean_symbol}'")
            
        raw_exchange = meta.get("fullExchangeName", "NSE")
        exchange = "NSE" if "NSE" in raw_exchange or "NSI" in raw_exchange else "BSE"

        # 3. Resolve Company and Instrument
        comp_meta = self._company_metadata.get(clean_symbol, {
            "name": f"{clean_symbol} Limited",
            "sector": "Unknown",
            "industry": "Unknown",
            "website": None
        })
        company, _ = Company.objects.update_or_create(
            short_name=clean_symbol,
            defaults={
                "name": comp_meta["name"],
                "sector": comp_meta["sector"],
                "industry": comp_meta["industry"],
                "website": comp_meta["website"],
                "is_active": True
            }
        )
        instrument, _ = Instrument.objects.update_or_create(
            company=company,
            symbol=clean_symbol,
            exchange=exchange,
            defaults={
                "instrument_type": "EQUITY",
                "currency": "INR",
                "is_active": True
            }
        )

        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        quote_lists = indicators.get("quote", [{}])[0]
        
        opens = quote_lists.get("open", [])
        highs = quote_lists.get("high", [])
        lows = quote_lists.get("low", [])
        closes = quote_lists.get("close", [])
        volumes = quote_lists.get("volume", [])
        
        n_bars = len(timestamps)
        normalized_bars = []
        
        # Note: Stored OHLCV is unadjusted because Yahoo Finance Chart API returns unadjusted
        # prices in its main quote dictionary. This is documented in the design specifications.
        
        now_utc = datetime.now(timezone.utc)
        
        # 4. Normalize & Validate each bar
        for i in range(n_bars):
            # Check for null values on holiday/halt bars and skip
            if (opens[i] is None or highs[i] is None or 
                lows[i] is None or closes[i] is None or 
                volumes[i] is None):
                continue
                
            t_epoch = timestamps[i]
            t = datetime.fromtimestamp(t_epoch, tz=timezone.utc)
            
            o = Decimal(str(opens[i]))
            h = Decimal(str(highs[i]))
            l = Decimal(str(lows[i]))
            c = Decimal(str(closes[i]))
            v = int(volumes[i])
            
            # Numeric quality gates (Phase 3)
            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                raise ValueError(f"Data Quality Error: Negative or zero price at timestamp {t}")
            if v < 0:
                raise ValueError(f"Data Quality Error: Negative volume detected at timestamp {t}")
                
            # OHLC consistency validation
            if l > h:
                raise ValueError(f"Data Quality Error: low ({l}) exceeds high ({h}) at timestamp {t}")
            if o > h or c > h:
                raise ValueError(f"Data Quality Error: open/close exceeds high at timestamp {t}")
            if o < l or c < l:
                raise ValueError(f"Data Quality Error: open/close is below low at timestamp {t}")
                
            # Future timestamp skew check (5 mins)
            if t > now_utc + timedelta(minutes=5):
                raise ValueError(f"Data Quality Error: future timestamp {t} exceeds current system clock.")
                
            normalized_bars.append({
                "timestamp": t,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v
            })

        # 5. Persist bars in bulk to maintain idempotency
        bar_timestamps = [b["timestamp"] for b in normalized_bars]
        existing_timestamps = set(OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe=timeframe,
            timestamp__in=bar_timestamps
        ).values_list('timestamp', flat=True))

        bars_to_create = []
        for b in normalized_bars:
            if b["timestamp"] not in existing_timestamps:
                bars_to_create.append(OHLCVBar(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=b["timestamp"],
                    open=b["open"],
                    high=b["high"],
                    low=b["low"],
                    close=b["close"],
                    volume=b["volume"],
                    source="YFinanceMarketProvider"
                ))

        if bars_to_create:
            OHLCVBar.objects.bulk_create(bars_to_create, batch_size=1000)
            logger.info(f"Ingested {len(bars_to_create)} new historical bars for {instrument.symbol}.")
        else:
            logger.info(f"All fetched bars already exist for {instrument.symbol}. Skipped duplicate insertion.")

        # Return all bars for the instrument/timeframe
        return list(OHLCVBar.objects.filter(instrument=instrument, timeframe=timeframe).order_by('timestamp'))

    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 500) -> List[OHLCVBar]:
        """
        Retrieves stored historical OHLCV bars sorted chronologically (oldest to newest).
        """
        try:
            instrument = Instrument.objects.get(symbol=symbol.strip().upper())
            return list(OHLCVBar.objects.filter(
                instrument=instrument,
                timeframe=timeframe
            ).order_by('-timestamp')[:limit])[::-1]
        except Instrument.DoesNotExist:
            return []

    def calculate_features(self, symbol: str, timeframe: str = "1d") -> int:
        """
        Calculates and persists derived technical features for the symbol.
        """
        try:
            instrument = Instrument.objects.get(symbol=symbol.strip().upper())
            engine = TechnicalFeatureEngine()
            return engine.calculate_and_save_features(instrument, timeframe)
        except Instrument.DoesNotExist:
            return 0

    def get_stored_features(self, symbol: str, timeframe: str = "1d", name: Optional[str] = None) -> List[TechnicalFeature]:
        """
        Retrieves stored derived features from database.
        """
        try:
            instrument = Instrument.objects.get(symbol=symbol.strip().upper())
            query = TechnicalFeature.objects.filter(instrument=instrument, timeframe=timeframe)
            if name:
                query = query.filter(name=name)
            return list(query.order_by('timestamp'))
        except Instrument.DoesNotExist:
            return []

    def refresh_features(self, symbol: str, timeframe: str = "1d") -> int:
        """
        Updates database bars first by querying fresh data, then recalculates features.
        """
        # Fetch fresh history (defaults to 1 year backfill to establish warmup)
        self.fetch_and_save_historical_ohlcv(symbol, timeframe)
        # Recalculate indicators
        return self.calculate_features(symbol, timeframe)
