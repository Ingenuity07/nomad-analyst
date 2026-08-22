# Module 4 — News & Event Intelligence Foundation

This document defines the architectural guidelines, persistent database models, deduplication mechanisms, entity resolution, and point-in-time querying constraints of the **News & Event Intelligence Foundation** module (Module 4).

---

## 1. Selected Data Sources
*   **Initial Source**: Yahoo Finance RSS Headline Feeds.
*   **RSS URL Target**: `https://finance.yahoo.com/rss/headline?s={symbol}.NS`
*   **Capabilities**: Yields headline title, full link URL, publication date (pubDate), short summary description, and GUID reference tag.
*   **Limitations**: Coverage varies; RSS represents syndication-heavy feeds.

---

## 2. News Provider Abstraction
Ingestion is wrapped inside the `YahooRSSNewsProvider` class inside [`market/providers/news_provider.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/providers/news_provider.py). Standard XML RSS attributes are parsed cleanly, validating that headlines are never empty.

---

## 3. Persistent Database Models

### NewsItem
Stores news articles collected from syndicates:
*   `company`: ForeignKey to `Company` (optional, to support market-wide or unresolved articles).
*   `instrument`: ForeignKey to `Instrument` (optional).
*   `headline`: Clean string headline.
*   `summary`: Body description paragraph.
*   `source`: CharField (e.g. `yahoo_rss`).
*   `source_id`: Ticker/Unique GUID from provider.
*   `url`: Link to full story.
*   `published_at`: Timezone-aware publication datetime.
*   `ingested_at`: UTC timestamp of database insertion.
*   `event_type`: Categorized event group.
*   `content_hash`: Unique SHA-256 hash.

### CorporateDisclosure
Separate model representing official company regulatory releases (Board meetings, results filings, investor reports):
*   `company`: ForeignKey to `Company`.
*   `headline`: Announcements title string.
*   `category`: Disclosure category (e.g. Board Meetings, Press Release).
*   `source`: BSE or NSE regulatory filing index.
*   `announcement_id`: Official reference ID.
*   `url`: Link to PDF/disclosure page.
*   `published_at`: Datetime of filing release.
*   `content_hash`: Uniqueness checksum.

---

## 4. Event Classification Taxonomy
Articles are deterministic classified upon ingestion using keyword mappings:
*   `earnings/results`: results, earnings, quarterly, financial performance.
*   `dividend`: dividend, interim, payout.
*   `bonus`: bonus issue, bonus shares.
*   `split`: stock split, share split.
*   `merger/acquisition`: merger, acquisition, acquire, takeover.
*   `management change`: ceo, cfo, resignation, appointment, board change.
*   `order/win`: wins order, bagged contract, contract win, bagged order.
*   `regulatory`: sebi, rbi, penalty, compliance.
*   `litigation`: court, lawsuit, dispute, supreme court.
*   `fundraising/debt`: fundraising, bonds, rights issue.
*   `expansion/capex`: capex, capacity expansion, new facility.
*   `product/business development`: launches, product launch.
*   `rating change`: downgrade, upgrade.
*   `analyst/broker action`: brokerage view, buy rating, target price.
*   `macro/market`: inflation, monetary policy, budget.
*   `other`: default classification.

---

## 5. Entity Resolution
*   **Resolution Strategy**: Maps incoming news ticker suffixes or company short names to our database `Company` and `Instrument` entities.
*   **Safety Boundary**: If symbol mapping fails or is highly ambiguous, the ForeignKey is left as `Null` (saved as unresolved market-wide news) instead of guessing.

---

## 6. Deduplication
*   **Mechanism**: Strict content hashing: `sha256(url + headline + published_at)`.
*   **Ingestion Guard**: Duplicate articles are ignored using `ignore_conflicts=True` inside Django bulk creation transactions.

---

## 7. Point-in-Time (PIT) Safety Guarantees
*   **Core Principle**: Backtesting look-ahead leakage is prevented by separating `published_at` (historical timeline event) from `ingested_at`.
*   **Query Constraint**: All historical news queries support an `as_of` parameter. Queries filter out any future articles where `published_at > as_of`.

---

## 8. Query Service
Exposed via `NewsIntelligenceService` inside [`market/services/news_service.py`](file:///Users/shivamsingh/personal/nomad-analyst/market/services/news_service.py):
*   `get_company_news(company_id, start_date, end_date, as_of)`
*   `get_company_events(company_id, event_type, as_of)`
*   `get_market_news(start_date, end_date, as_of)`

---

## 9. Tools Layer
Exposes deterministic structured facts to LLM researchers:
*   `get_company_news`: fetches limited news list for ticker.
*   `get_company_events`: retrieves categorized events list.
*   `get_market_news`: retrieves market-wide general headlines.
