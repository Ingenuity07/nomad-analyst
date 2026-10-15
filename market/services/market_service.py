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
        
        # Sector and metadata mapping for all NIFTY 50 constituents + indices.
        # Source: data/universe/nifty50_constituents_2026-09-03.json
        # Extended to cover all 50 equities so that fetch_and_save_historical_ohlcv
        # does not overwrite bootstrapped Company records with "Unknown" sector/industry.
        self._company_metadata = {
            # ── NIFTY 50 Equities ─────────────────────────────────────────────
            "ADANIENT":   {"name": "Adani Enterprises Limited",                    "sector": "Diversified",          "industry": "Diversified Conglomerate",          "website": "https://www.adanienterprises.com"},
            "ADANIPORTS": {"name": "Adani Ports and Special Economic Zone Limited", "sector": "Infrastructure",       "industry": "Port & Logistics",                  "website": "https://www.adaniports.com"},
            "APOLLOHOSP": {"name": "Apollo Hospitals Enterprise Limited",           "sector": "Healthcare",           "industry": "Hospitals & Healthcare Services",    "website": "https://www.apollohospitals.com"},
            "ASIANPAINT": {"name": "Asian Paints Limited",                          "sector": "Consumer Staples",     "industry": "Paints & Coatings",                 "website": "https://www.asianpaints.com"},
            "AXISBANK":   {"name": "Axis Bank Limited",                             "sector": "Financial Services",   "industry": "Private Banking",                   "website": "https://www.axisbank.com"},
            "BAJAJ-AUTO": {"name": "Bajaj Auto Limited",                            "sector": "Automobile",           "industry": "2-3 Wheelers",                      "website": "https://www.bajajauto.com"},
            "BAJFINANCE": {"name": "Bajaj Finance Limited",                         "sector": "Financial Services",   "industry": "Non-Banking Financial Company",     "website": "https://www.bajajfinserv.in"},
            "BAJAJFINSV": {"name": "Bajaj Finserv Limited",                         "sector": "Financial Services",   "industry": "Diversified Financial Services",    "website": "https://www.bajajfinserv.in"},
            "BPCL":       {"name": "Bharat Petroleum Corporation Limited",          "sector": "Energy",               "industry": "Oil & Gas Refining & Marketing",    "website": "https://www.bharatpetroleum.in"},
            "BHARTIARTL": {"name": "Bharti Airtel Limited",                         "sector": "Telecommunications",   "industry": "Telecom Services",                  "website": "https://www.airtel.in"},
            "BRITANNIA":  {"name": "Britannia Industries Limited",                  "sector": "Consumer Staples",     "industry": "Food Products",                     "website": "https://www.britannia.co.in"},
            "CIPLA":      {"name": "Cipla Limited",                                 "sector": "Pharmaceutical",       "industry": "Pharmaceuticals",                   "website": "https://www.cipla.com"},
            "COALINDIA":  {"name": "Coal India Limited",                            "sector": "Metals & Mining",      "industry": "Coal & Consumable Fuels",           "website": "https://www.coalindia.in"},
            "DIVISLAB":   {"name": "Divi's Laboratories Limited",                   "sector": "Pharmaceutical",       "industry": "Pharmaceuticals",                   "website": "https://www.divislab.com"},
            "DRREDDY":    {"name": "Dr. Reddy's Laboratories Limited",              "sector": "Pharmaceutical",       "industry": "Pharmaceuticals",                   "website": "https://www.drreddys.com"},
            "EICHERMOT":  {"name": "Eicher Motors Limited",                         "sector": "Automobile",           "industry": "2-3 Wheelers",                      "website": "https://www.eichermotors.com"},
            "GRASIM":     {"name": "Grasim Industries Limited",                     "sector": "Diversified",          "industry": "Diversified Industrials",           "website": "https://www.grasim.com"},
            "HCLTECH":    {"name": "HCL Technologies Limited",                      "sector": "Technology",           "industry": "IT Services & Consulting",          "website": "https://www.hcltech.com"},
            "HDFCBANK":   {"name": "HDFC Bank Limited",                             "sector": "Financial Services",   "industry": "Private Banking",                   "website": "https://www.hdfcbank.com"},
            "HDFCLIFE":   {"name": "HDFC Life Insurance Company Limited",           "sector": "Financial Services",   "industry": "Insurance",                         "website": "https://www.hdfclife.com"},
            "HEROMOTOCO": {"name": "Hero MotoCorp Limited",                         "sector": "Automobile",           "industry": "2-3 Wheelers",                      "website": "https://www.heromotocorp.com"},
            "HINDALCO":   {"name": "Hindalco Industries Limited",                   "sector": "Metals & Mining",      "industry": "Aluminium",                         "website": "https://www.hindalco.com"},
            "HINDUNILVR": {"name": "Hindustan Unilever Limited",                    "sector": "Consumer Staples",     "industry": "Personal Products",                 "website": "https://www.hul.co.in"},
            "ICICIBANK":  {"name": "ICICI Bank Limited",                            "sector": "Financial Services",   "industry": "Private Banking",                   "website": "https://www.icicibank.com"},
            "INDUSINDBK": {"name": "IndusInd Bank Limited",                         "sector": "Financial Services",   "industry": "Private Banking",                   "website": "https://www.indusind.com"},
            "INFY":       {"name": "Infosys Limited",                               "sector": "Technology",           "industry": "IT Services & Consulting",          "website": "https://www.infosys.com"},
            "ITC":        {"name": "ITC Limited",                                   "sector": "Consumer Staples",     "industry": "Tobacco",                           "website": "https://www.itcportal.com"},
            "JSWSTEEL":   {"name": "JSW Steel Limited",                             "sector": "Metals & Mining",      "industry": "Steel",                             "website": "https://www.jsw.in/steel"},
            "KOTAKBANK":  {"name": "Kotak Mahindra Bank Limited",                   "sector": "Financial Services",   "industry": "Private Banking",                   "website": "https://www.kotak.com"},
            "LT":         {"name": "Larsen & Toubro Limited",                       "sector": "Infrastructure",       "industry": "Engineering & Construction",         "website": "https://www.larsentoubro.com"},
            "M&M":        {"name": "Mahindra & Mahindra Limited",                   "sector": "Automobile",           "industry": "Cars & Utility Vehicles",           "website": "https://www.mahindra.com"},
            "MARUTI":     {"name": "Maruti Suzuki India Limited",                   "sector": "Automobile",           "industry": "Cars & Utility Vehicles",           "website": "https://www.marutisuzuki.com"},
            "NESTLEIND":  {"name": "Nestle India Limited",                          "sector": "Consumer Staples",     "industry": "Food Products",                     "website": "https://www.nestle.in"},
            "NTPC":       {"name": "NTPC Limited",                                  "sector": "Power",                "industry": "Electric Utilities",                "website": "https://www.ntpc.co.in"},
            "ONGC":       {"name": "Oil and Natural Gas Corporation Limited",       "sector": "Energy",               "industry": "Oil & Gas Exploration & Production", "website": "https://www.ongcindia.com"},
            "POWERGRID":  {"name": "Power Grid Corporation of India Limited",       "sector": "Power",                "industry": "Electric Utilities",                "website": "https://www.powergridindia.com"},
            "RELIANCE":   {"name": "Reliance Industries Limited",                   "sector": "Energy",               "industry": "Oil & Gas - Integrated",            "website": "https://www.ril.com"},
            "SBILIFE":    {"name": "SBI Life Insurance Company Limited",            "sector": "Financial Services",   "industry": "Insurance",                         "website": "https://www.sbilife.co.in"},
            "SHRIRAMFIN": {"name": "Shriram Finance Limited",                       "sector": "Financial Services",   "industry": "Non-Banking Financial Company",     "website": "https://www.shriramfinance.in"},
            "SBIN":       {"name": "State Bank of India",                           "sector": "Financial Services",   "industry": "Public Banking",                    "website": "https://www.sbi.co.in"},
            "SUNPHARMA":  {"name": "Sun Pharmaceutical Industries Limited",         "sector": "Pharmaceutical",       "industry": "Pharmaceuticals",                   "website": "https://www.sunpharma.com"},
            "TCS":        {"name": "Tata Consultancy Services Limited",             "sector": "Technology",           "industry": "IT Services & Consulting",          "website": "https://www.tcs.com"},
            "TATACONSUM": {"name": "Tata Consumer Products Limited",                "sector": "Consumer Staples",     "industry": "Food Products",                     "website": "https://www.tataconsumer.com"},
            "TATAMOTORS": {"name": "Tata Motors Limited",                           "sector": "Automobile",           "industry": "Commercial Vehicles",               "website": "https://www.tatamotors.com"},
            "TATASTEEL":  {"name": "Tata Steel Limited",                            "sector": "Metals & Mining",      "industry": "Steel",                             "website": "https://www.tatasteel.com"},
            "TECHM":      {"name": "Tech Mahindra Limited",                         "sector": "Technology",           "industry": "IT Services & Consulting",          "website": "https://www.techmahindra.com"},
            "TITAN":      {"name": "Titan Company Limited",                         "sector": "Consumer Discretionary", "industry": "Specialty Retail",                "website": "https://www.titancompany.in"},
            "TRENT":      {"name": "Trent Limited",                                 "sector": "Consumer Discretionary", "industry": "Specialty Retail",                "website": "https://www.trентlimited.com"},
            "ULTRACEMCO": {"name": "UltraTech Cement Limited",                      "sector": "Cement",               "industry": "Construction Materials",            "website": "https://www.ultratechcement.com"},
            "WIPRO":      {"name": "Wipro Limited",                                 "sector": "Technology",           "industry": "IT Services & Consulting",          "website": "https://www.wipro.com"},

            # ── Index / Macro / Global indicators ────────────────────────────
            "^NSEI":    {"name": "Nifty 50 Index",                  "sector": "Index",        "industry": "Index",           "website": None},
            "^NSEBANK": {"name": "Nifty Bank Index",                "sector": "Index",        "industry": "Index",           "website": None},
            "^BSESN":   {"name": "S&P BSE SENSEX",                  "sector": "Index",        "industry": "Index",           "website": None},
            "^CNXIT":   {"name": "Nifty IT Index",                  "sector": "Index",        "industry": "Index",           "website": None},
            "^GSPC":    {"name": "S&P 500 Index",                   "sector": "Global Index", "industry": "Global Index",    "website": None},
            "^IXIC":    {"name": "Nasdaq Composite Index",          "sector": "Global Index", "industry": "Global Index",    "website": None},
            "^DJI":     {"name": "Dow Jones Industrial Average",    "sector": "Global Index", "industry": "Global Index",    "website": None},
            "^VIX":     {"name": "CBOE Volatility Index",           "sector": "Global Index", "industry": "Global Index",    "website": None},
            "USDINR=X": {"name": "USD/INR Exchange Rate",           "sector": "Currency",     "industry": "Currency",        "website": None},
            "CL=F":     {"name": "Crude Oil Futures",               "sector": "Commodity",    "industry": "Commodity",       "website": None},
            "GC=F":     {"name": "Gold Futures",                    "sector": "Commodity",    "industry": "Commodity",       "website": None},
            "^TNX":     {"name": "US 10-Year Treasury Yield",       "sector": "Macro",        "industry": "Interest Rate",   "website": None},
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
        if clean_symbol.startswith("^"):
            instrument_type = "INDEX"
            if clean_symbol in ("^NSEI", "^NSEBANK", "^CNXSC", "^CNXIT"):
                exchange = "NSE"
                currency = "INR"
            elif clean_symbol == "^BSESN":
                exchange = "BSE"
                currency = "INR"
            else:
                exchange = "GLOBAL"
                currency = "USD"
        elif "=" in clean_symbol or clean_symbol in ("CL=F", "GC=F"):
            instrument_type = "INDEX"
            exchange = "GLOBAL"
            currency = "INR" if "USDINR" in clean_symbol else "USD"
        else:
            instrument_type = "EQUITY"
            exchange = canonical_quote.exchange
            currency = "INR"

        instrument, _ = Instrument.objects.update_or_create(
            company=company,
            symbol=clean_symbol,
            defaults={
                "exchange": exchange,
                "instrument_type": instrument_type,
                "currency": currency,
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
        if clean_symbol == "TMPV" or symbol.strip().upper() in ("TATAMOTORS", "TATAMOTORS.NS"):
            clean_symbol = "TATAMOTORS"
        if not clean_symbol or not re.match(r"^[A-Za-z0-9_\-\^=&]+$", clean_symbol):
            raise ValueError(f"Invalid symbol characters: '{clean_symbol}'")
            
        # Determine exchange, instrument type and currency
        if clean_symbol.startswith("^"):
            instrument_type = "INDEX"
            if clean_symbol in ("^NSEI", "^NSEBANK", "^CNXSC", "^CNXIT"):
                exchange = "NSE"
                currency = "INR"
            elif clean_symbol == "^BSESN":
                exchange = "BSE"
                currency = "INR"
            else:
                exchange = "GLOBAL"
                currency = "USD"
        elif "=" in clean_symbol or clean_symbol in ("CL=F", "GC=F"):
            instrument_type = "INDEX"
            exchange = "GLOBAL"
            currency = "INR" if "USDINR" in clean_symbol else "USD"
        else:
            instrument_type = "EQUITY"
            currency = "INR"
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
            defaults={
                "exchange": exchange,
                "instrument_type": instrument_type,
                "currency": currency,
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

    def get_historical_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 500, as_of: Optional[datetime] = None) -> List[OHLCVBar]:
        """
        Retrieves stored historical OHLCV bars sorted chronologically (oldest to newest).
        """
        try:
            instrument = Instrument.objects.get(symbol=symbol.strip().upper())
            query = OHLCVBar.objects.filter(
                instrument=instrument,
                timeframe=timeframe
            )
            if as_of:
                query = query.filter(timestamp__lte=as_of)
            return list(query.order_by('-timestamp')[:limit])[::-1]
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

    def get_stored_features(self, symbol: str, timeframe: str = "1d", name: Optional[str] = None, as_of: Optional[datetime] = None) -> List[TechnicalFeature]:
        """
        Retrieves stored derived features from database.
        """
        try:
            instrument = Instrument.objects.get(symbol=symbol.strip().upper())
            query = TechnicalFeature.objects.filter(instrument=instrument, timeframe=timeframe)
            if name:
                query = query.filter(name=name)
            if as_of:
                query = query.filter(timestamp__lte=as_of)
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
