import logging
from datetime import datetime, timezone
import hashlib
import email.utils
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils.timezone import make_aware

from market.models import Company, Instrument, NewsItem, CorporateDisclosure
from market.providers.news_provider import YahooRSSNewsProvider
from market.exceptions import SymbolNotFoundError

logger = logging.getLogger(__name__)

# Deterministic keywords classifier dictionary
EVENT_CLASSIFICATION_RULES = {
    "earnings/results": ["results", "earnings", "quarterly", "financial performance", "q1", "q2", "q3", "q4", "net profit rises", "net profit falls"],
    "dividend": ["dividend", "interim dividend", "payout"],
    "bonus": ["bonus issue", "bonus shares", "allotment of bonus"],
    "split": ["stock split", "share split", "sub-division of shares"],
    "merger/acquisition": ["merger", "acquisition", "acquire", "takeover", "amalgamation", "stake buy", "stake sale"],
    "management change": ["ceo", "cfo", "resigns", "resignation", "appoints", "appointment", "board change", "managing director", "md change"],
    "order/win": ["wins order", "bagged contract", "awarded contract", "secured order", "order win", "contract win", "bags contract", "bagged order", "bags USD"],
    "regulatory": ["sebi", "rbi", "penalty", "show cause", "cci", "regulator", "compliance"],
    "litigation": ["court", "lawsuit", "dispute", "litigation", "supreme court", "high court", "tribunal"],
    "fundraising/debt": ["fundraising", "bonds", "rights issue", "qip", "ncd", "issue of shares", "debt raise"],
    "expansion/capex": ["capex", "capacity expansion", "plant setup", "expansion plan", "new facility"],
    "product/business development": ["launches", "product launch", "new business", "entry into"],
    "rating change": ["downgrade", "upgrade", "rating action", "crisil", "icra", "fitch", "moody"],
    "analyst/broker action": ["brokerage view", "target price", "buy rating", "sell rating", "neutral view", "brokerage action"],
    "macro/market": ["inflation", "budget", "monetary policy", "interest rates", "macro economy"]
}

class NewsIntelligenceService:
    """
    Handles company news fetching, entity mapping, deterministic deduplication,
    event classification, and point-in-time safe historical querying.
    """

    def __init__(self, provider=None):
        self.provider = provider or YahooRSSNewsProvider()

    def fetch_and_save_company_news(self, symbol: str) -> List[NewsItem]:
        """
        Fetches RSS news feed for target symbol, normalizes items, classifies them,
        resolves the target Company entity, and saves them safely checking content hashes.
        """
        raw_items = self.provider.fetch_company_news(symbol)
        
        # Entity Resolution
        clean_symbol = symbol.strip().upper().split('.')[0]
        try:
            company = Company.objects.get(short_name=clean_symbol)
        except Company.DoesNotExist:
            logger.warning(f"NewsService: failed to resolve Company for symbol '{clean_symbol}'. News saved as unresolved.")
            company = None

        instrument = Instrument.objects.filter(symbol=clean_symbol).first()

        saved_items = []
        for raw in raw_items:
            # 1. Parse date (point-in-time safety requirement: do not use ingestion time)
            pub_date = self._parse_publication_date(raw["published_at_raw"])
            
            # 2. Deterministic classification
            event_type = self._classify_event(raw["headline"], raw["summary"])

            # 3. Content hash calculation for strict deduplication
            content_hash = self._generate_content_hash(raw["url"], raw["headline"], pub_date)

            # 4. Ingestion validation: skip if already exists
            if NewsItem.objects.filter(content_hash=content_hash).exists():
                continue

            item = NewsItem(
                company=company,
                instrument=instrument,
                headline=raw["headline"],
                summary=raw["summary"],
                source=raw["source"],
                source_id=raw["source_id"],
                url=raw["url"],
                published_at=pub_date,
                event_type=event_type,
                raw_metadata=raw,
                content_hash=content_hash
            )
            saved_items.append(item)

        if saved_items:
            with transaction.atomic():
                NewsItem.objects.bulk_create(saved_items, ignore_conflicts=True)
            logger.info(f"NewsService: saved {len(saved_items)} new news articles for symbol '{symbol}'.")

        return saved_items

    def get_company_news(self, company_id: Any, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, as_of: Optional[datetime] = None) -> List[NewsItem]:
        """
        Queries news for a company within dates. Enforces point-in-time safety via as_of.
        """
        query = NewsItem.objects.filter(company_id=company_id)
        
        if start_date:
            query = query.filter(published_at__gte=start_date)
        if end_date:
            query = query.filter(published_at__lte=end_date)
            
        # Point-in-time guard: exclude future data relative to as_of
        if as_of:
            query = query.filter(published_at__lte=as_of)

        return list(query.order_by('-published_at'))

    def get_company_events(self, company_id: Any, event_type: str, as_of: Optional[datetime] = None) -> List[NewsItem]:
        """
        Queries company events filtered by event category.
        """
        query = NewsItem.objects.filter(company_id=company_id, event_type=event_type)
        if as_of:
            query = query.filter(published_at__lte=as_of)
        return list(query.order_by('-published_at'))

    def get_market_news(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, as_of: Optional[datetime] = None) -> List[NewsItem]:
        """
        Queries market-wide news (including unresolved news).
        """
        query = NewsItem.objects.all()
        if start_date:
            query = query.filter(published_at__gte=start_date)
        if end_date:
            query = query.filter(published_at__lte=end_date)
        if as_of:
            query = query.filter(published_at__lte=as_of)
        return list(query.order_by('-published_at'))

    def _parse_publication_date(self, pub_date_str: str) -> datetime:
        """
        Safely parses standard RSS pubDate string into timezone-aware datetime.
        Defaults to current UTC time if parsing fails.
        """
        if not pub_date_str:
            return datetime.now(timezone.utc)
        try:
            dt = email.utils.parsedate_to_datetime(pub_date_str)
            # Make sure it's aware
            if dt.tzinfo is None:
                dt = make_aware(dt, timezone.utc)
            return dt
        except Exception:
            try:
                # Fallback parser
                from dateutil import parser
                dt = parser.parse(pub_date_str)
                if dt.tzinfo is None:
                    dt = make_aware(dt, timezone.utc)
                return dt
            except Exception:
                return datetime.now(timezone.utc)

    def _classify_event(self, headline: str, summary: str) -> str:
        """
        Uses deterministic keyword matches to classify article category.
        """
        text = f"{headline} {summary or ''}".lower()
        for category, keywords in EVENT_CLASSIFICATION_RULES.items():
            for word in keywords:
                if word in text:
                    return category
        return "other"

    def _generate_content_hash(self, url: str, headline: str, published_at: datetime) -> str:
        """
        Generates unique content hash for deduplication.
        """
        key_string = f"{url or ''}:{headline}:{published_at.isoformat()}"
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
