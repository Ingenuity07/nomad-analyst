import logging
import math
import numpy as np
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from django.utils import timezone as django_timezone
from django.db.models import Max, Q
from market.models import (
    Instrument,
    OHLCVBar,
    TechnicalFeature,
    DerivedFundamentalMetric,
    Company,
    IncomeStatement,
    NewsItem,
    CorporateDisclosure,
    Universe,
    UniverseMembership,
    StockOpportunitySnapshot,
    MarketContextSnapshot
)

logger = logging.getLogger(__name__)

DEFAULT_OPPORTUNITY_CONFIG = {
    "DELIVERY_SWING": {
        "weights": {
            "technical": 0.40,
            "fundamental": 0.20,
            "sector": 0.20,
            "market": 0.10,
            "news": 0.10
        },
        "filters": {
            "min_volume_30d_avg": 5000,
            "min_turnover_30d_avg": 1000000.0,  # 10 Lakhs INR
        }
    },
    "LONG_TERM": {
        "weights": {
            "technical": 0.10,
            "fundamental": 0.50,
            "sector": 0.20,
            "market": 0.10,
            "news": 0.10
        },
        "filters": {
            "min_volume_30d_avg": 2000,
            "min_turnover_30d_avg": 500000.0,   # 5 Lakhs INR
        }
    }
}


class OpportunityDiscoveryService:
    """
    Deterministic service that calculates stock intelligence feature fusion,
    scores candidates based on configurable parameters, classifies opportunities,
    ranks them by investment horizons, and persists snapshots cleanly.
    Calculations are 100% PIT-safe and batch-optimized to avoid N+1 queries.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DEFAULT_OPPORTUNITY_CONFIG

    def _parse_as_of(self, as_of: Any) -> datetime:
        if not as_of:
            return django_timezone.now()
        if isinstance(as_of, str):
            try:
                dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
                if django_timezone.is_naive(dt):
                    return django_timezone.make_aware(dt, timezone.utc)
                return dt
            except ValueError:
                raise ValueError(f"Invalid as_of timestamp format: {as_of}")
        if isinstance(as_of, datetime):
            if django_timezone.is_naive(as_of):
                return django_timezone.make_aware(as_of, timezone.utc)
            return as_of
        raise ValueError(f"Unsupported as_of type: {type(as_of)}")

    def scan_universe(self, universe_name: str, horizon: str, as_of: Any = None) -> List[StockOpportunitySnapshot]:
        """
        Executes opportunity scanning and scoring for all instruments in a given universe.
        Returns a list of saved StockOpportunitySnapshot records.
        """
        dt_as_of = self._parse_as_of(as_of)
        
        # 1. Investigate investment horizon routing
        if horizon == "INTRADAY":
            logger.info("Intraday horizon requested. Intraday capability is currently NOT READY.")
            return []

        if horizon not in ("DELIVERY_SWING", "LONG_TERM"):
            raise ValueError(f"Unsupported investment horizon: {horizon}")

        horizon_config = self.config[horizon]
        
        # 2. Load universe instruments
        univ = Universe.objects.filter(name=universe_name, is_active=True).first()
        if not univ:
            # Fallback to all active equities if universe not explicitly found in DB
            logger.warning(f"Universe '{universe_name}' not found. Defaulting to all active equities.")
            instruments = list(Instrument.objects.select_related('company').filter(instrument_type="EQUITY", is_active=True))
        else:
            memberships = UniverseMembership.objects.select_related('instrument__company').filter(
                universe=univ,
                is_active=True,
                added_at__lte=dt_as_of
            ).filter(Q(removed_at__isnull=True) | Q(removed_at__gt=dt_as_of))
            instruments = [m.instrument for m in memberships if m.instrument.is_active]

        if not instruments:
            logger.warning(f"No active instruments found in universe '{universe_name}' as of {dt_as_of}")
            return []

        # 3. Batch retrieve required data to eliminate N+1 queries
        # Latest OHLCVBar
        latest_ts = OHLCVBar.objects.filter(
            instrument__in=instruments,
            timestamp__lte=dt_as_of
        ).values('instrument').annotate(max_ts=Max('timestamp'))
        
        ts_map = {item['instrument']: item['max_ts'] for item in latest_ts}
        bars = []
        if ts_map:
            q_bar = Q()
            for inst_id, ts in ts_map.items():
                q_bar |= Q(instrument_id=inst_id, timestamp=ts)
            bars = list(OHLCVBar.objects.filter(q_bar))
        latest_bars = {bar.instrument_id: bar for bar in bars}

        # 30-day liquidity window
        start_liquidity = dt_as_of - timedelta(days=45)
        recent_bars = list(OHLCVBar.objects.filter(
            instrument__in=instruments,
            timestamp__range=(start_liquidity, dt_as_of)
        ).order_by('instrument', '-timestamp'))
        
        recent_bars_by_inst = {}
        for bar in recent_bars:
            recent_bars_by_inst.setdefault(bar.instrument_id, []).append(bar)

        liquidity_metrics = {}
        for inst_id, inst_bars in recent_bars_by_inst.items():
            window_bars = inst_bars[:30]
            if window_bars:
                avg_vol = float(np.mean([float(b.volume) for b in window_bars]))
                avg_val = float(np.mean([float(b.close * b.volume) for b in window_bars]))
                liquidity_metrics[inst_id] = {
                    "avg_volume_30d": avg_vol,
                    "avg_turnover_30d": avg_val
                }

        # Latest TechnicalFeatures
        latest_tf_ts = TechnicalFeature.objects.filter(
            instrument__in=instruments,
            timestamp__lte=dt_as_of
        ).values('instrument').annotate(max_ts=Max('timestamp'))
        
        tf_ts_map = {item['instrument']: item['max_ts'] for item in latest_tf_ts}
        tf_records = []
        if tf_ts_map:
            q_tf = Q()
            for inst_id, ts in tf_ts_map.items():
                q_tf |= Q(instrument_id=inst_id, timestamp=ts)
            tf_records = list(TechnicalFeature.objects.filter(q_tf))
            
        tf_by_inst = {}
        for tf in tf_records:
            tf_by_inst.setdefault(tf.instrument_id, {})[tf.name] = float(tf.value) if tf.value is not None else None

        # Latest MarketContextSnapshot
        mkt_snapshot = MarketContextSnapshot.objects.filter(as_of__lte=dt_as_of).order_by('-as_of').first()
        
        # Latest visible Fundamental metrics (respecting PIT constraints)
        companies = [inst.company for inst in instruments]
        visible_statements = IncomeStatement.objects.filter(
            company__in=companies,
            period_type="ANNUAL",
            period_end__lte=dt_as_of.date()
        )
        
        company_visible_periods = {}
        for stmt in visible_statements:
            company_visible_periods.setdefault(stmt.company_id, []).append(stmt.period_string)

        all_periods = []
        for p_list in company_visible_periods.values():
            all_periods.extend(p_list)

        fundamental_metrics = {comp.id: {} for comp in companies}
        if all_periods:
            metrics = DerivedFundamentalMetric.objects.filter(
                company__in=companies,
                period_type="ANNUAL",
                period_string__in=all_periods
            )
            metrics_by_comp = {}
            for m in metrics:
                comp_metrics = metrics_by_comp.setdefault(m.company_id, {})
                if m.name not in comp_metrics or m.period_string > comp_metrics[m.name]["period"]:
                    comp_metrics[m.name] = {
                        "value": float(m.value) if m.value is not None else None,
                        "period": m.period_string
                    }
            for comp_id, comp_m in metrics_by_comp.items():
                fundamental_metrics[comp_id] = {k: v["value"] for k, v in comp_m.items()}

        # Recent economic and news events (last 14 days)
        start_news = dt_as_of - timedelta(days=14)
        news_items = list(NewsItem.objects.filter(
            company__in=companies,
            published_at__range=(start_news, dt_as_of)
        ))
        disclosures = list(CorporateDisclosure.objects.filter(
            company__in=companies,
            published_at__range=(start_news, dt_as_of)
        ))
        
        events_by_company = {}
        for item in news_items:
            events_by_company.setdefault(item.company_id, []).append({
                "headline": item.headline,
                "type": "news",
                "published_at": item.published_at
            })
        for disc in disclosures:
            events_by_company.setdefault(disc.company_id, []).append({
                "headline": disc.headline,
                "type": "disclosure",
                "published_at": disc.published_at
            })

        # 4. Calculate stock scores, classifications and save snapshots
        snapshots_to_create = []
        for inst in instruments:
            bar = latest_bars.get(inst.id)
            tf = tf_by_inst.get(inst.id, {})
            liq = liquidity_metrics.get(inst.id, {"avg_volume_30d": 0.0, "avg_turnover_30d": 0.0})
            fun = fundamental_metrics.get(inst.company_id, {})
            events = events_by_company.get(inst.company_id, [])

            # Filter candidates based on liquidity specification
            min_vol = horizon_config["filters"].get("min_volume_30d_avg", 0)
            min_turn = horizon_config["filters"].get("min_turnover_30d_avg", 0.0)
            if liq["avg_volume_30d"] < min_vol or liq["avg_turnover_30d"] < min_turn:
                logger.info(f"XYZ symbol '{inst.symbol}' skipped due to liquidity filters.")
                continue

            # Evaluate Data Quality & Stale boundaries
            quality_status = "COMPLETE"
            missing_fields = []
            if not bar:
                quality_status = "INSUFFICIENT_MARKET_DATA"
                missing_fields.append("latest_bar")
            elif (dt_as_of - bar.timestamp) > timedelta(days=5):
                quality_status = "STALE"
                missing_fields.append("latest_bar_5d_stale")

            if not tf:
                quality_status = "INSUFFICIENT_HISTORY"
                missing_fields.append("technical_features")
            else:
                for k in ("SMA_50", "SMA_200", "RSI_14"):
                    if tf.get(k) is None:
                        quality_status = "PARTIAL"
                        missing_fields.append(f"technical_feature_{k}")

            if not fun:
                quality_status = "INSUFFICIENT_FUNDAMENTALS"
                missing_fields.append("fundamental_metrics")
            else:
                for k in ("revenue_growth_yoy", "return_on_equity", "debt_equity"):
                    if fun.get(k) is None:
                        quality_status = "PARTIAL"
                        missing_fields.append(f"fundamental_metric_{k}")

            data_quality = {
                "status": quality_status,
                "missing_fields": missing_fields,
                "notes": "Evaluation of availability of required technical and fundamental indicators."
            }

            # 5. Core component scoring
            close_val = float(bar.close) if bar and bar.close else 0.0
            
            # A. Technical Score (0 to 100)
            tech_score = 50.0
            if tf:
                trend_score = 0.0
                sma50 = tf.get("SMA_50")
                sma200 = tf.get("SMA_200")
                if sma50 and sma200:
                    if close_val > sma50 and close_val > sma200 and sma50 > sma200:
                        trend_score = 100.0
                    elif close_val > sma50 or close_val > sma200:
                        trend_score = 50.0
                
                rsi = tf.get("RSI_14")
                mom_score = 50.0
                if rsi is not None:
                    if 55 <= rsi <= 70:
                        mom_score = 100.0
                    elif 45 <= rsi < 55:
                        mom_score = 70.0
                    elif rsi > 70:
                        mom_score = 40.0
                    else:
                        mom_score = 20.0
                
                # Relative volume & distance from high
                rel_vol = tf.get("relative_volume_20")
                dist_high = tf.get("distance_from_high_20")
                vol_high_score = 50.0
                rv_sub = 50.0
                dh_sub = 50.0
                if rel_vol is not None:
                    rv_sub = 100.0 if rel_vol > 1.5 else (70.0 if rel_vol > 1.0 else 40.0)
                if dist_high is not None:
                    # dist_high is negative or zero, e.g. -2.0 means 2% below high
                    dh_sub = 100.0 if dist_high > -2.0 else (80.0 if dist_high > -5.0 else 40.0)
                vol_high_score = 0.5 * rv_sub + 0.5 * dh_sub
                
                tech_score = 0.5 * trend_score + 0.3 * mom_score + 0.2 * vol_high_score

            # B. Fundamental Score (0 to 100)
            fun_score = 50.0
            if fun:
                # Growth
                rev_g = fun.get("revenue_growth_yoy", 0.0)
                pat_g = fun.get("pat_growth_yoy", 0.0)
                growth_sub = 50.0
                if rev_g is not None and pat_g is not None:
                    rg_val = 100.0 if rev_g > 0.20 else (70.0 if rev_g > 0.10 else (50.0 if rev_g > 0.0 else 20.0))
                    pg_val = 100.0 if pat_g > 0.20 else (70.0 if pat_g > 0.10 else (50.0 if pat_g > 0.0 else 20.0))
                    growth_sub = 0.4 * rg_val + 0.6 * pg_val
                
                # Profitability
                roe = fun.get("return_on_equity")
                net_m = fun.get("net_margin")
                prof_sub = 50.0
                if roe is not None and net_m is not None:
                    roe_val = 100.0 if roe > 0.18 else (70.0 if roe > 0.12 else 40.0)
                    nm_val = 100.0 if net_m > 0.15 else (70.0 if net_m > 0.08 else 40.0)
                    prof_sub = 0.5 * roe_val + 0.5 * nm_val
                
                # Efficiency & Debt
                roce = fun.get("return_on_capital_employed")
                de = fun.get("debt_equity")
                eff_sub = 50.0
                if roce is not None and de is not None:
                    roce_val = 100.0 if roce > 0.18 else (70.0 if roce > 0.12 else 40.0)
                    de_val = 100.0 if de < 0.5 else (70.0 if de < 1.0 else (50.0 if de < 1.5 else 20.0))
                    eff_sub = 0.5 * roce_val + 0.5 * de_val
                
                fun_score = 0.3 * growth_sub + 0.3 * prof_sub + 0.4 * eff_sub

            # C. Sector Score (0 to 100)
            sec_score = 50.0
            sector_name = inst.company.sector
            sector_rank_info = None
            if mkt_snapshot and mkt_snapshot.sector_rankings and sector_name:
                for sec_item in mkt_snapshot.sector_rankings:
                    if sec_item.get("sector") == sector_name:
                        sector_rank_info = sec_item
                        break
            
            if sector_rank_info:
                tier = sector_rank_info.get("tier", "neutral")
                mom_state = sector_rank_info.get("momentum_state", "stable")
                if tier == "strongest":
                    sec_score = 100.0
                elif tier == "weakest":
                    sec_score = 20.0
                else:
                    sec_score = 80.0 if mom_state == "improving" else (60.0 if mom_state == "stable" else 40.0)

            # D. Market Alignment (0 to 100)
            mkt_align = 50.0
            nifty_trend = "sideways"
            if mkt_snapshot and mkt_snapshot.index_regimes:
                nifty_trend = mkt_snapshot.index_regimes.get("^NSEI", {}).get("trend", "sideways")
            
            if tf:
                sma50 = tf.get("SMA_50")
                sma200 = tf.get("SMA_200")
                stock_trend = "sideways"
                if sma50 and sma200:
                    if close_val > sma200 and sma50 > sma200:
                        stock_trend = "bullish"
                    elif close_val < sma200 and sma50 < sma200:
                        stock_trend = "bearish"
                
                if stock_trend == nifty_trend:
                    mkt_align = 100.0
                elif stock_trend == "bullish" and nifty_trend == "sideways":
                    mkt_align = 80.0
                else:
                    mkt_align = 40.0

            # E. News Score (0 to 100)
            news_score = 70.0
            recent_pos = False
            recent_neg = False
            for ev in events:
                headline_lower = ev["headline"].lower()
                # Positive triggers
                if any(x in headline_lower for x in ("rise", "dividend", "order win", "bags", "growth", "surges", "profit rises")):
                    recent_pos = True
                # Negative triggers
                if any(x in headline_lower for x in ("drop", "falls", "loss", "penalty", "investigation", "crashes", "profit falls")):
                    recent_neg = True
            
            if recent_pos:
                news_score = 100.0
            elif recent_neg:
                news_score = 30.0

            # Combine Scores deterministically
            weights = horizon_config["weights"]
            final_score = (
                tech_score * weights["technical"] +
                fun_score * weights["fundamental"] +
                sec_score * weights["sector"] +
                mkt_align * weights["market"] +
                news_score * weights["news"]
            )

            # 6. Opportunity Classifications
            opp_type = "NONE"
            if tf:
                # 1. TRENDING
                if tech_score > 70.0 and close_val > tf.get("SMA_50", 0.0):
                    opp_type = "TRENDING"
                # 2. MOMENTUM
                elif tf.get("RSI_14", 50.0) > 60.0 and tf.get("relative_volume_20", 1.0) > 1.2:
                    opp_type = "MOMENTUM"
                # 3. BREAKOUT WATCH
                elif tf.get("distance_from_high_20", -10.0) > -2.0 and tf.get("relative_volume_20", 1.0) > 1.1:
                    opp_type = "BREAKOUT_WATCH"
                # 4. FUNDAMENTAL QUALITY
                elif fun.get("return_on_equity", 0.0) > 0.15 and fun.get("debt_equity", 2.0) < 1.0:
                    opp_type = "FUNDAMENTAL_QUALITY"
                # 5. FUNDAMENTAL + MOMENTUM
                elif fun.get("return_on_equity", 0.0) > 0.12 and close_val > tf.get("SMA_50", 0.0) and tf.get("RSI_14", 50.0) > 50.0:
                    opp_type = "FUNDAMENTAL_MOMENTUM"
                # 6. SECTOR LEADER
                elif sector_rank_info and sector_rank_info.get("tier") == "strongest" and tech_score > 70.0:
                    opp_type = "SECTOR_LEADER"
                # 7. EVENT DRIVEN
                elif events:
                    opp_type = "EVENT_DRIVEN"
                # 8. CONTRARIAN / RECOVERY
                elif tf.get("RSI_14", 50.0) < 35.0 and fun.get("revenue_growth_yoy", 0.0) > 0.10:
                    opp_type = "CONTRARIAN_RECOVERY"

            # 7. Generate Pros & Cons
            pros = []
            cons = []
            
            if tf:
                sma50 = tf.get("SMA_50")
                sma200 = tf.get("SMA_200")
                if sma50 and close_val > sma50:
                    pros.append("Price is trading above its 50-day SMA")
                else:
                    cons.append("Price is trading below its 50-day SMA")
                    
                if sma200 and close_val > sma200:
                    pros.append("Long-term trend is bullish (above 200-day SMA)")
                else:
                    cons.append("Long-term trend is bearish (below 200-day SMA)")

                rsi = tf.get("RSI_14")
                if rsi is not None:
                    if rsi > 60:
                        pros.append(f"Strong momentum support (RSI={rsi:.1f})")
                    elif rsi < 35:
                        cons.append(f"Oversold territory (RSI={rsi:.1f})")
            
            if fun:
                roe = fun.get("return_on_equity")
                de = fun.get("debt_equity")
                rev_g = fun.get("revenue_growth_yoy")
                
                if roe is not None:
                    if roe > 0.15:
                        pros.append(f"High capital return efficiency (ROE={roe * 100:.1f}%)")
                    else:
                        cons.append(f"Low capital return efficiency (ROE={roe * 100:.1f}%)")
                if de is not None:
                    if de < 0.8:
                        pros.append(f"Safe leverage structure (Debt/Equity={de:.2f})")
                    else:
                        cons.append(f"Elevated balance-sheet leverage (Debt/Equity={de:.2f})")
                if rev_g is not None:
                    if rev_g > 0.10:
                        pros.append(f"Positive growth trajectory (Revenue Growth={rev_g * 100:.1f}%)")
                    else:
                        cons.append(f"Slowing growth trajectory (Revenue Growth={rev_g * 100:.1f}%)")

            if sector_rank_info:
                tier = sector_rank_info.get("tier", "neutral")
                if tier == "strongest":
                    pros.append(f"Sector '{sector_name}' is a top-performing market leader")
                elif tier == "weakest":
                    cons.append(f"Sector '{sector_name}' is lagging market averages")

            if recent_pos:
                pros.append("Recent material positive event or news item noted")
            if recent_neg:
                cons.append("Recent material negative event or news risk noted")

            supporting_features = {
                "close": close_val,
                "volume": int(bar.volume) if bar and bar.volume else 0,
                "technical_features": tf,
                "fundamental_metrics": fun,
                "sector_rank_info": sector_rank_info,
                "recent_events_count": len(events),
                "pros": pros
            }

            # 8. Accumulate snapshot object for bulk write
            snapshot = StockOpportunitySnapshot(
                instrument=inst,
                as_of=dt_as_of,
                universe=universe_name,
                horizon=horizon,
                opportunity_type=opp_type,
                component_scores={
                    "technical": round(tech_score, 2),
                    "fundamental": round(fun_score, 2),
                    "sector": round(sec_score, 2),
                    "market": round(mkt_align, 2),
                    "news": round(news_score, 2),
                    "liquidity": round(float(liq["avg_turnover_30d"]), 2)
                },
                final_opportunity_score=Decimal(f"{final_score:.4f}"),
                supporting_features=supporting_features,
                risks=cons,
                data_quality=data_quality,
                calculation_version=1
            )
            snapshots_to_create.append(snapshot)

        # 9. Perform batch write with transaction atomic guarantee
        from django.db import transaction
        with transaction.atomic():
            StockOpportunitySnapshot.objects.filter(
                instrument__in=[s.instrument for s in snapshots_to_create],
                as_of=dt_as_of,
                universe=universe_name,
                horizon=horizon
            ).delete()
            if snapshots_to_create:
                StockOpportunitySnapshot.objects.bulk_create(snapshots_to_create)

        return snapshots_to_create
