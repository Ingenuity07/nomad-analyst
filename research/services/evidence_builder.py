import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from django.utils import timezone as dj_timezone
from market.models import (
    Company,
    Instrument,
    StockIntradayContext,
    IntradayOpportunitySnapshot,
    MarketContextSnapshot,
    StockOpportunitySnapshot,
    DerivedFundamentalMetric,
    IncomeStatement,
    CorporateEvent,
    NewsItem,
    TechnicalFeature
)

logger = logging.getLogger(__name__)

# Configurable deterministic evidence selection limits
DEFAULT_RECENT_NEWS_LIMIT = 5
DEFAULT_RECENT_EVENTS_LIMIT = 5
DEFAULT_QUARTER_LIMIT = 4
DEFAULT_ANNUAL_LIMIT = 3
STALENESS_THRESHOLD_MINUTES = 30


class ResearchEvidencePackageBuilder:
    """
    Deterministically gathers, normalizes, validates, and packages all available
    Nomad intelligence before any LLM is called.

    Preserves source provenance, timestamps, data freshness, and transparently
    reports missing fields and audit limitations without fabricating data.
    """

    def __init__(
        self,
        news_limit: int = DEFAULT_RECENT_NEWS_LIMIT,
        events_limit: int = DEFAULT_RECENT_EVENTS_LIMIT,
        quarter_limit: int = DEFAULT_QUARTER_LIMIT,
        annual_limit: int = DEFAULT_ANNUAL_LIMIT,
    ):
        self.news_limit = news_limit
        self.events_limit = events_limit
        self.quarter_limit = quarter_limit
        self.annual_limit = annual_limit

    def build_package(
        self,
        symbol: str,
        mode: str = "INTRADAY",
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Builds a complete, normalized, structured evidence package.
        """
        now = as_of or dj_timezone.now()
        clean_symbol = symbol.strip().upper()
        
        # 1. Resolve Instrument and Company
        instrument = Instrument.objects.filter(symbol__iexact=clean_symbol).select_related('company').first()
        company = instrument.company if instrument else Company.objects.filter(short_name__iexact=clean_symbol).first()
        
        missing_data: List[str] = []

        company_info = {
            "symbol": clean_symbol,
            "name": company.name if company else clean_symbol,
            "sector": company.sector if company else "UNKNOWN",
            "industry": company.industry if company else "UNKNOWN",
            "status": "AVAILABLE" if company else "UNAVAILABLE",
            "source": "DATABASE"
        }
        if not company:
            missing_data.append("company_profile")

        # 2. Market Context Snapshot
        market_context_data = self._gather_market_context(now, missing_data)

        # 3. Sector Context
        sector_context_data = self._gather_sector_context(company_info["sector"], market_context_data, missing_data)

        # 4. Stock & Opportunity Context
        opp_data = {}
        stock_context = {}
        if mode == "INTRADAY":
            opp_data, stock_context = self._gather_intraday_data(instrument, clean_symbol, now, missing_data)
        elif mode == "LONG_TERM":
            opp_data, stock_context = self._gather_long_term_data(instrument, company, now, missing_data)
        else: # GENERAL
            opp_data, stock_context = self._gather_general_data(instrument, company, now, missing_data)

        # 5. Fundamentals (for LONG_TERM and GENERAL modes, lightweight for INTRADAY)
        fundamentals_data = self._gather_fundamentals(company, mode, missing_data)

        # 6. Recent News & Events
        news_data = self._gather_news(company, now)
        events_data = self._gather_events(company, now)

        # 7. Data Quality & Freshness Assessment
        data_quality = {
            "overall_status": "HIGH" if len(missing_data) <= 1 else ("MEDIUM" if len(missing_data) <= 3 else "LOW"),
            "coverage_pct": max(0, 100 - (len(missing_data) * 15)),
            "missing_data": missing_data,
            "package_generated_at": now.isoformat(),
            "as_of": now.isoformat(),
        }

        # 8. Deterministic Summary (Generated with ZERO LLM calls)
        deterministic_summary = self._generate_deterministic_summary(
            symbol=clean_symbol,
            mode=mode,
            company=company_info,
            opportunity=opp_data,
            market=market_context_data,
            sector=sector_context_data
        )

        package = {
            "research_mode": mode,
            "asset": clean_symbol,
            "timestamp": now.isoformat(),
            "company": company_info,
            "opportunity": opp_data,
            "stock_context": stock_context,
            "market_context": market_context_data,
            "sector_context": sector_context_data,
            "fundamentals": fundamentals_data,
            "recent_news": news_data,
            "recent_events": events_data,
            "data_quality": data_quality,
            "deterministic_summary": deterministic_summary
        }

        # Compute SHA-256 evidence hash
        package_str = json.dumps(package, sort_keys=True, default=str)
        evidence_hash = hashlib.sha256(package_str.encode("utf-8")).hexdigest()
        package["evidence_hash"] = evidence_hash

        return package

    def _gather_market_context(self, now: datetime, missing_data: List[str]) -> Dict[str, Any]:
        """Gathers latest market context and breadth state."""
        ctx = MarketContextSnapshot.objects.filter(as_of__lte=now).order_by('-as_of').first()
        if not ctx:
            missing_data.append("market_context")
            return {
                "status": "UNAVAILABLE",
                "source": "DERIVED_CALCULATION",
                "regime": "UNKNOWN",
                "direction": "UNKNOWN",
                "breadth_state": "UNKNOWN",
                "advances": None,
                "declines": None,
                "advance_decline_ratio": None,
                "nifty_return_pct": None,
                "banknifty_return_pct": None,
                "pct_above_vwap": None,
                "timestamp": None,
                "freshness": "UNAVAILABLE"
            }

        age_seconds = (now - ctx.as_of).total_seconds()
        is_stale = age_seconds > (STALENESS_THRESHOLD_MINUTES * 60)

        # Extract returns from columns or index_regimes
        nifty_ret = float(ctx.nifty_return) if ctx.nifty_return is not None else None
        banknifty_ret = float(ctx.banknifty_return) if ctx.banknifty_return is not None else None
        if nifty_ret is None and ctx.index_regimes and isinstance(ctx.index_regimes, dict):
            nifty_ret = ctx.index_regimes.get("NIFTY", {}).get("return_pct")
            banknifty_ret = ctx.index_regimes.get("BANKNIFTY", {}).get("return_pct")

        advances = ctx.advance_count if ctx.advance_count else (ctx.breadth.get("advances") if ctx.breadth else None)
        declines = ctx.decline_count if ctx.decline_count else (ctx.breadth.get("declines") if ctx.breadth else None)
        ad_ratio = float(ctx.advance_decline_ratio) if ctx.advance_decline_ratio is not None else (ctx.breadth.get("advance_decline_ratio") if ctx.breadth else None)
        pct_above_vwap = float(ctx.above_vwap_pct) if ctx.above_vwap_pct is not None else (ctx.breadth.get("pct_above_vwap") if ctx.breadth else None)

        regime_val = getattr(ctx, 'market_regime', None) or getattr(ctx, 'regime', 'UNKNOWN')
        dir_val = getattr(ctx, 'market_direction', None) or getattr(ctx, 'direction', 'UNKNOWN')

        return {
            "status": "AVAILABLE",
            "source": "KITE_MARKET_FEED",
            "regime": regime_val,
            "direction": dir_val,
            "market_volatility": ctx.market_volatility,
            "breadth_state": ctx.breadth_state,
            "advances": advances,
            "declines": declines,
            "advance_decline_ratio": ad_ratio,
            "nifty_return_pct": nifty_ret,
            "banknifty_return_pct": banknifty_ret,
            "pct_above_vwap": pct_above_vwap,
            "sector_rankings": ctx.sector_rankings[:5] if ctx.sector_rankings else [],
            "timestamp": ctx.as_of.isoformat(),
            "age_minutes": round(age_seconds / 60, 1),
            "freshness": "STALE" if is_stale else "FRESH"
        }

    def _gather_sector_context(self, sector_name: str, market_ctx: Dict[str, Any], missing_data: List[str]) -> Dict[str, Any]:
        """Extracts sector ranking and rotation context."""
        rankings = market_ctx.get("sector_rankings", [])
        if not sector_name or sector_name == "UNKNOWN" or not rankings:
            return {
                "sector": sector_name,
                "rank": None,
                "status": "UNAVAILABLE" if not rankings else "AVAILABLE",
                "return_pct": None,
                "breadth": None,
                "momentum": "UNKNOWN",
                "source": "DERIVED_CALCULATION"
            }

        for item in rankings:
            name = item.get("sector") or item.get("sector_name") or ""
            if sector_name.lower() in name.lower() or name.lower() in sector_name.lower():
                return {
                    "sector": name,
                    "rank": item.get("rank"),
                    "status": "AVAILABLE",
                    "return_pct": item.get("return_pct"),
                    "breadth": item.get("breadth") or item.get("advance_decline_ratio"),
                    "momentum": item.get("momentum_state") or item.get("momentum", "NEUTRAL"),
                    "source": "DERIVED_CALCULATION"
                }

        return {
            "sector": sector_name,
            "rank": None,
            "status": "AVAILABLE",
            "return_pct": None,
            "breadth": None,
            "momentum": "NEUTRAL",
            "source": "DERIVED_CALCULATION"
        }

    def _gather_intraday_data(
        self,
        instrument: Optional[Instrument],
        symbol: str,
        now: datetime,
        missing_data: List[str]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Gathers latest IntradayOpportunitySnapshot and StockIntradayContext."""
        opp_data = {}
        stock_context = {}

        # 1. Latest IntradayOpportunitySnapshot
        opp_snap = IntradayOpportunitySnapshot.objects.filter(
            symbol__iexact=symbol,
            timestamp__lte=now
        ).order_by('-timestamp').first()

        if opp_snap:
            age_seconds = (now - opp_snap.timestamp).total_seconds()
            opp_data = {
                "status": "AVAILABLE",
                "source": "INTRADAY_OPPORTUNITY_ENGINE",
                "opportunity_type": opp_snap.opportunity_type,
                "state": opp_snap.state,
                "score": float(opp_snap.score),
                "confidence": float(opp_snap.confidence),
                "rank": opp_snap.rank,
                "bias": opp_snap.metrics.get("bias", "BULLISH") if opp_snap.metrics else "BULLISH",
                "component_scores": {
                    "momentum": float(opp_snap.momentum_score),
                    "relative_strength": float(opp_snap.relative_strength_score),
                    "volume": float(opp_snap.volume_score),
                    "vwap": float(opp_snap.vwap_score),
                    "market_alignment": float(opp_snap.market_alignment_score),
                    "sector_alignment": float(opp_snap.sector_alignment_score),
                    "orb": float(opp_snap.orb_score),
                    "data_quality": float(opp_snap.data_quality_score),
                },
                "supporting_factors": opp_snap.supporting_factors,
                "contradicting_factors": opp_snap.contradicting_factors,
                "warnings": opp_snap.warnings,
                "penalties": opp_snap.penalties,
                "invalidation_condition": opp_snap.metrics.get("invalidation_condition") if opp_snap.metrics else None,
                "market_alignment": opp_snap.market_alignment,
                "sector_alignment": opp_snap.sector_alignment,
                "timestamp": opp_snap.timestamp.isoformat(),
                "freshness": "STALE" if age_seconds > (STALENESS_THRESHOLD_MINUTES * 60) else "FRESH",
            }
        else:
            missing_data.append("intraday_opportunity_snapshot")
            opp_data = {
                "status": "UNAVAILABLE",
                "source": "INTRADAY_OPPORTUNITY_ENGINE",
                "opportunity_type": "NONE",
                "state": "NONE",
                "score": None,
                "confidence": None,
                "rank": None,
                "component_scores": {},
                "supporting_factors": [],
                "contradicting_factors": [],
                "warnings": ["No active intraday opportunity snapshot detected for this symbol."],
                "freshness": "UNAVAILABLE"
            }

        # 2. Latest StockIntradayContext / Metrics
        ctx = None
        if instrument:
            ctx = StockIntradayContext.objects.filter(
                instrument=instrument,
                timestamp__lte=now
            ).order_by('-timestamp').first()

        if ctx:
            stock_context = {
                "status": "AVAILABLE",
                "source": "KITE_LIVE_FEED",
                "last_price": float(ctx.last_price) if ctx.last_price is not None else None,
                "change_pct": float(ctx.change_pct) if ctx.change_pct is not None else None,
                "vwap": float(ctx.vwap) if ctx.vwap is not None else None,
                "distance_from_vwap": float(ctx.distance_from_vwap) if ctx.distance_from_vwap is not None else None,
                "volume": ctx.volume,
                "relative_volume": float(ctx.relative_volume) if ctx.relative_volume is not None else None,
                "momentum_5m": float(ctx.momentum_5m) if ctx.momentum_5m is not None else None,
                "momentum_15m": float(ctx.momentum_15m) if ctx.momentum_15m is not None else None,
                "momentum_30m": float(ctx.momentum_30m) if ctx.momentum_30m is not None else None,
                "relative_strength_vs_market": float(ctx.relative_strength_vs_market) if ctx.relative_strength_vs_market is not None else None,
                "relative_strength_vs_sector": float(ctx.relative_strength_vs_sector) if ctx.relative_strength_vs_sector is not None else None,
                "volume_confirmation": ctx.volume_confirmation,
                "opening_range_state": ctx.opening_range_state,
                "intraday_high": float(ctx.intraday_high) if ctx.intraday_high is not None else None,
                "intraday_low": float(ctx.intraday_low) if ctx.intraday_low is not None else None,
                "timestamp": ctx.timestamp.isoformat(),
            }
        elif opp_snap and opp_snap.metrics:
            # Fallback to metrics saved on the opportunity snapshot
            m = opp_snap.metrics
            stock_context = {
                "status": "AVAILABLE",
                "source": "OPPORTUNITY_METRICS_SNAPSHOT",
                "last_price": m.get("last_price"),
                "change_pct": m.get("change_pct"),
                "vwap": m.get("vwap"),
                "distance_from_vwap": m.get("vwap_diff_pct"),
                "volume": m.get("volume"),
                "relative_volume": m.get("relative_volume"),
                "momentum_5m": m.get("momentum_5m"),
                "momentum_15m": m.get("momentum_15m"),
                "momentum_30m": m.get("momentum_30m"),
                "relative_strength_vs_market": m.get("relative_strength_vs_market"),
                "relative_strength_vs_sector": m.get("relative_strength_vs_sector"),
                "volume_confirmation": m.get("volume_confirmation", "NEUTRAL"),
                "opening_range_state": m.get("opening_range_state", "INSIDE_ORB"),
                "timestamp": opp_snap.timestamp.isoformat(),
            }
        else:
            missing_data.append("stock_intraday_context")
            stock_context = {
                "status": "UNAVAILABLE",
                "source": "KITE_LIVE_FEED",
                "last_price": None,
                "change_pct": None,
                "vwap": None,
                "distance_from_vwap": None,
                "momentum_5m": None,
                "momentum_15m": None,
                "relative_strength_vs_market": None,
                "volume_confirmation": "UNKNOWN",
                "opening_range_state": "UNKNOWN",
            }

        return opp_data, stock_context

    def _gather_long_term_data(
        self,
        instrument: Optional[Instrument],
        company: Optional[Company],
        now: datetime,
        missing_data: List[str]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Gathers Horizon v1 opportunity and technical baseline."""
        opp_data = {}
        stock_context = {}

        if instrument:
            snap = StockOpportunitySnapshot.objects.filter(
                instrument=instrument,
                horizon='LONG_TERM',
                as_of__lte=now
            ).order_by('-as_of').first()

            if snap:
                opp_data = {
                    "status": "AVAILABLE",
                    "source": "HORIZON_OPPORTUNITY_SNAPSHOT",
                    "opportunity_type": snap.opportunity_type,
                    "score": float(snap.final_opportunity_score),
                    "component_scores": snap.component_scores,
                    "supporting_features": snap.supporting_features,
                    "risks": snap.risks,
                    "timestamp": snap.as_of.isoformat(),
                    "horizon_v1_audit_notes": [
                        "Bank and NBFC metrics require domain-specific interpretation (generic Debt/Equity is not applicable).",
                        "Discovery score favors static mature quality and may penalize capital-intensive turnaround leaders.",
                        "Annual metrics may reflect cyclical earnings peaks.",
                        "P/E ratio is tracked in fundamental metrics but is not a component of the legacy opportunity score."
                    ]
                }
            else:
                missing_data.append("horizon_opportunity_snapshot")
                opp_data = {
                    "status": "UNAVAILABLE",
                    "score": None,
                    "opportunity_type": "NONE",
                    "horizon_v1_audit_notes": ["No legacy long-term opportunity snapshot found."]
                }

            # Technical features
            tech_feats = {}
            for name in ['SMA_50', 'SMA_200', 'RSI_14', 'MACD', 'ATR_14']:
                feat = TechnicalFeature.objects.filter(
                    instrument=instrument,
                    name=name,
                    timestamp__lte=now
                ).order_by('-timestamp').first()
                if feat and feat.value is not None:
                    tech_feats[name] = float(feat.value)
            stock_context = {
                "status": "AVAILABLE" if tech_feats else "UNAVAILABLE",
                "technical_features": tech_feats,
                "source": "TECHNICAL_CALCULATION"
            }
        else:
            missing_data.append("instrument_record")
            opp_data = {"status": "UNAVAILABLE"}
            stock_context = {"status": "UNAVAILABLE"}

        return opp_data, stock_context

    def _gather_general_data(
        self,
        instrument: Optional[Instrument],
        company: Optional[Company],
        now: datetime,
        missing_data: List[str]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Gathers general overview context."""
        intraday_opp, intraday_ctx = self._gather_intraday_data(instrument, company.short_name if company else "", now, [])
        long_term_opp, tech_ctx = self._gather_long_term_data(instrument, company, now, [])

        opp_data = {
            "status": "AVAILABLE",
            "intraday": intraday_opp,
            "long_term": long_term_opp
        }
        stock_context = {
            "status": "AVAILABLE",
            "intraday_metrics": intraday_ctx,
            "technical_features": tech_ctx.get("technical_features", {})
        }
        return opp_data, stock_context

    def _gather_fundamentals(
        self,
        company: Optional[Company],
        mode: str,
        missing_data: List[str]
    ) -> Dict[str, Any]:
        """Gathers derived fundamental ratios and latest annual/quarterly statements."""
        if not company:
            missing_data.append("fundamentals")
            return {"status": "UNAVAILABLE", "source": "FUNDAMENTAL_DATABASE"}

        # Gather derived metrics (ROE, ROCE, Debt/Equity, P/E, Margins)
        metrics_qs = DerivedFundamentalMetric.objects.filter(company=company)
        metrics_map: Dict[str, Any] = {}
        for m in metrics_qs:
            metrics_map[f"{m.name}_{m.period_type}_{m.period_string}"] = float(m.value) if m.value is not None else None

        # Gather latest statements
        income_statements = []
        annual_stmts = IncomeStatement.objects.filter(
            company=company,
            period_type='ANNUAL'
        ).order_by('-fiscal_year')[:self.annual_limit]

        for s in annual_stmts:
            income_statements.append({
                "period": f"FY{s.fiscal_year} ({s.period_string})",
                "revenue": float(s.revenue) if s.revenue is not None else None,
                "ebitda": float(s.ebitda) if s.ebitda is not None else None,
                "pbt": float(s.pbt) if s.pbt is not None else None,
                "source": "COMPANY_ANNUAL_REPORT"
            })

        quarterly_stmts = []
        if mode in ("LONG_TERM", "GENERAL"):
            q_stmts = IncomeStatement.objects.filter(
                company=company,
                period_type='QUARTERLY'
            ).order_by('-period_end')[:self.quarter_limit]

            for qs in q_stmts:
                quarterly_stmts.append({
                    "period": qs.period_string,
                    "revenue": float(qs.revenue) if qs.revenue is not None else None,
                    "ebitda": float(qs.ebitda) if qs.ebitda is not None else None,
                    "pbt": float(qs.pbt) if qs.pbt is not None else None,
                    "source": "COMPANY_QUARTERLY_REPORT"
                })

        return {
            "status": "AVAILABLE" if (metrics_map or income_statements) else "UNAVAILABLE",
            "source": "FUNDAMENTAL_DATABASE",
            "derived_metrics": metrics_map,
            "annual_statements": income_statements,
            "quarterly_statements": quarterly_stmts,
            "audit_guidance": "Verify whether cyclical commodity highs or non-operating income affect recent margin trends."
        }

    def _gather_news(self, company: Optional[Company], now: datetime) -> List[Dict[str, Any]]:
        """Gathers recent material news items within deterministic limit."""
        if not company:
            return []
        news_items = NewsItem.objects.filter(
            company=company,
            published_at__lte=now
        ).order_by('-published_at')[:self.news_limit]

        out = []
        for n in news_items:
            sentiment_val = getattr(n, 'sentiment', None)
            if not sentiment_val and hasattr(n, 'raw_metadata') and isinstance(n.raw_metadata, dict):
                sentiment_val = n.raw_metadata.get('sentiment', 'NEUTRAL')
            out.append({
                "headline": n.headline,
                "source": n.source,
                "source_type": "NEWS_SOURCE",
                "sentiment": sentiment_val or "NEUTRAL",
                "published_at": n.published_at.isoformat() if n.published_at else None
            })
        return out

    def _gather_events(self, company: Optional[Company], now: datetime) -> List[Dict[str, Any]]:
        """Gathers corporate actions/events within deterministic limit."""
        if not company:
            return []
        events = CorporateEvent.objects.filter(
            company=company
        ).order_by('-ex_date', '-announcement_date')[:self.events_limit]

        out = []
        for ev in events:
            out.append({
                "event_type": ev.event_type,
                "source_type": "CORPORATE_EVENT",
                "announcement_date": ev.announcement_date.isoformat() if ev.announcement_date else None,
                "ex_date": ev.ex_date.isoformat() if ev.ex_date else None,
                "details": ev.details
            })
        return out

    def _generate_deterministic_summary(
        self,
        symbol: str,
        mode: str,
        company: Dict[str, Any],
        opportunity: Dict[str, Any],
        market: Dict[str, Any],
        sector: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates a concise deterministic summary prior to calling any LLM.
        Adheres to Section 43 of the specification.
        """
        score = opportunity.get("score")
        rank = opportunity.get("rank")
        opp_type = opportunity.get("opportunity_type", "NONE")
        opp_state = opportunity.get("state", "NONE")
        confidence = opportunity.get("confidence")

        supporting_cnt = len(opportunity.get("supporting_factors", []))
        contradicting_cnt = len(opportunity.get("contradicting_factors", []))
        warnings_cnt = len(opportunity.get("warnings", []))

        return {
            "symbol": symbol,
            "mode": mode,
            "opportunity_type": opp_type,
            "opportunity_state": opp_state,
            "opportunity_score": score,
            "opportunity_rank": rank,
            "confidence": confidence,
            "market_regime": market.get("regime", "UNKNOWN"),
            "market_breadth": market.get("breadth_state", "UNKNOWN"),
            "sector_name": sector.get("sector", "UNKNOWN"),
            "sector_rank": sector.get("rank"),
            "supporting_factors_count": supporting_cnt,
            "contradicting_factors_count": contradicting_cnt,
            "warnings_count": warnings_cnt,
            "generated_deterministically": True
        }
