import logging
import re
import numpy as np
import talib
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from django.utils import timezone as django_timezone
from django.db.models import Q
from market.models import Instrument, OHLCVBar, Company, CorporateEvent, NewsItem, CorporateDisclosure, MarketContextSnapshot

logger = logging.getLogger(__name__)

def get_indicators_pit(instrument: Instrument, as_of: datetime, timeframe: str = "1d") -> Dict[str, Any]:
    """
    Computes technical indicators on-the-fly for a given instrument up to `as_of` to ensure PIT safety.
    """
    bars = list(OHLCVBar.objects.filter(
        instrument=instrument,
        timeframe=timeframe,
        timestamp__lte=as_of
    ).order_by('timestamp'))
    
    n_bars = len(bars)
    if n_bars < 5:
        return {}

    # Extract price arrays
    closes = np.array([float(b.close) for b in bars], dtype=np.float64)
    highs = np.array([float(b.high) for b in bars], dtype=np.float64)
    lows = np.array([float(b.low) for b in bars], dtype=np.float64)
    volumes = np.array([float(b.volume) for b in bars], dtype=np.float64)

    # Trend Indicators
    sma20 = talib.SMA(closes, timeperiod=min(20, n_bars))[-1]
    sma50 = talib.SMA(closes, timeperiod=min(50, n_bars))[-1]
    sma200 = talib.SMA(closes, timeperiod=min(200, n_bars))[-1]
    
    # Momentum
    rsi14 = talib.RSI(closes, timeperiod=min(14, n_bars))[-1]
    
    macd_line, macd_sig = None, None
    if n_bars >= 26:
        macd, macdsignal, _ = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
        macd_line = macd[-1]
        macd_sig = macdsignal[-1]
    
    # Volatility
    atr14 = talib.ATR(highs, lows, closes, timeperiod=min(14, n_bars))[-1]
    
    # Daily Returns
    daily_returns = np.zeros_like(closes)
    if n_bars > 1:
        daily_returns[1:] = (closes[1:] - closes[:-1]) / closes[:-1]
    daily_return = daily_returns[-1]
    
    # Volatility (Rolling Std Dev of daily returns over 20 periods)
    vol20 = np.nan
    if n_bars >= 20:
        vol20 = np.std(daily_returns[-20:], ddof=1)
        
    # Volatility History for percentile calculation
    vol_history = []
    if n_bars >= 20:
        for i in range(20, n_bars + 1):
            vol_history.append(np.std(daily_returns[i-20:i], ddof=1))
            
    # Rolling 252-day High / Low
    high_252 = talib.MAX(highs, timeperiod=min(252, n_bars))[-1]
    low_252 = talib.MIN(lows, timeperiod=min(252, n_bars))[-1]

    # Map timestamps to daily returns for cross-market correlation
    daily_returns_map = {bars[i].timestamp.date(): daily_returns[i] for i in range(n_bars)}

    return {
        "close": closes[-1],
        "daily_return": daily_return,
        "daily_returns_map": daily_returns_map,
        "bar_timestamps": [b.timestamp for b in bars],
        "sma20": sma20 if not np.isnan(sma20) else None,
        "sma50": sma50 if not np.isnan(sma50) else None,
        "sma200": sma200 if not np.isnan(sma200) else None,
        "rsi14": rsi14 if not np.isnan(rsi14) else None,
        "macd_line": macd_line if macd_line is not None and not np.isnan(macd_line) else None,
        "macd_sig": macd_sig if macd_sig is not None and not np.isnan(macd_sig) else None,
        "atr14": atr14 if not np.isnan(atr14) else None,
        "vol20": vol20 if not np.isnan(vol20) else None,
        "vol_history": [v for v in vol_history if not np.isnan(v)],
        "high_252": high_252 if not np.isnan(high_252) else None,
        "low_252": low_252 if not np.isnan(low_252) else None,
    }


class MarketContextService:
    """
    Deterministic service that builds, retrieves, and persists broader market context.
    Strictly point-in-time safe relative to the configured 'as_of' timestamp.
    """

    def __init__(self):
        pass

    def _parse_as_of(self, as_of: Any) -> datetime:
        if not as_of:
            return django_timezone.now()
        if isinstance(as_of, str):
            # Parse ISO datetime
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

    def calculate_market_regime(self, index_symbol: str, as_of: datetime) -> Dict[str, Any]:
        """
        Calculates the trend, volatility, and momentum regime for a specific index.
        """
        inst = Instrument.objects.filter(symbol=index_symbol, is_active=True).first()
        if not inst:
            return {
                "symbol": index_symbol,
                "status": "unavailable",
                "error": f"Instrument '{index_symbol}' not found in database."
            }
            
        features = get_indicators_pit(inst, as_of)
        if not features or "close" not in features:
            return {
                "symbol": index_symbol,
                "status": "insufficient_data",
                "error": "Not enough historical bars available before as_of."
            }

        close = features["close"]
        sma50 = features["sma50"]
        sma200 = features["sma200"]
        rsi = features["rsi14"]
        macd_line = features["macd_line"]
        macd_sig = features["macd_sig"]
        vol20 = features["vol20"]
        vol_history = features["vol_history"]

        # 1. Trend Classification
        trend = "sideways"
        if sma50 and sma200:
            if close > sma200 and sma50 > sma200:
                trend = "bullish"
            elif close < sma200 and sma50 < sma200:
                trend = "bearish"

        # 2. Volatility Classification
        vol_regime = "normal"
        if vol20 is not None:
            if len(vol_history) >= 30:
                p25 = np.percentile(vol_history, 25)
                p75 = np.percentile(vol_history, 75)
                p95 = np.percentile(vol_history, 95)
                if vol20 < p25:
                    vol_regime = "low"
                elif vol20 < p75:
                    vol_regime = "normal"
                elif vol20 < p95:
                    vol_regime = "high"
                else:
                    vol_regime = "extreme"
            else:
                # Fallback to absolute daily returns std dev thresholds
                if vol20 < 0.008:
                    vol_regime = "low"
                elif vol20 < 0.018:
                    vol_regime = "normal"
                elif vol20 < 0.03:
                    vol_regime = "high"
                else:
                    vol_regime = "extreme"

        # 3. Momentum Classification
        momentum = "neutral"
        if rsi is not None:
            if rsi > 55 and (macd_line is None or macd_sig is None or macd_line > macd_sig):
                momentum = "positive"
            elif rsi < 45 and (macd_line is None or macd_sig is None or macd_line < macd_sig):
                momentum = "negative"

        return {
            "symbol": index_symbol,
            "status": "active",
            "close": round(close, 2),
            "trend": trend,
            "volatility": vol_regime,
            "momentum": momentum,
            "indicators": {
                "rsi14": round(rsi, 2) if rsi else None,
                "sma50": round(sma50, 2) if sma50 else None,
                "sma200": round(sma200, 2) if sma200 else None,
                "vol20": round(vol20, 6) if vol20 else None
            }
        }

    def calculate_market_breadth(self, universe: str, as_of: datetime) -> Dict[str, Any]:
        """
        Calculates breadth statistics for the active universe at as_of.
        """
        # Load active equities
        equities = Instrument.objects.filter(instrument_type="EQUITY", is_active=True)
        if universe != "ALL":
            # In our system, all active equities in DB are treated as the NIFTY50 / target universe
            pass

        total_universe = equities.count()
        if total_universe == 0:
            return {"status": "error", "error": "No instruments in universe"}

        advancing = 0
        declining = 0
        unchanged = 0
        above_sma20 = 0
        above_sma50 = 0
        above_sma200 = 0
        new_highs = 0
        new_lows = 0
        covered_count = 0
        missing_symbols = []

        for eq in equities:
            features = get_indicators_pit(eq, as_of)
            if not features or "close" not in features:
                missing_symbols.append(eq.symbol)
                continue
            
            covered_count += 1
            close = features["close"]
            ret = features["daily_return"]
            sma20 = features["sma20"]
            sma50 = features["sma50"]
            sma200 = features["sma200"]
            high_252 = features["high_252"]
            low_252 = features["low_252"]

            # Advancing / Declining
            if ret > 0:
                advancing += 1
            elif ret < 0:
                declining += 1
            else:
                unchanged += 1

            # SMA Participation
            if sma20 and close > sma20:
                above_sma20 += 1
            if sma50 and close > sma50:
                above_sma50 += 1
            if sma200 and close > sma200:
                above_sma200 += 1

            # New Highs / Lows (within 0.5% of 252-day high/low)
            if high_252 and close >= high_252 * 0.995:
                new_highs += 1
            if low_252 and close <= low_252 * 1.005:
                new_lows += 1

        if covered_count == 0:
            return {
                "status": "insufficient_data",
                "error": "No price bars available for any stocks in universe at this timestamp."
            }

        coverage_ratio = float(covered_count) / total_universe
        ad_ratio = float(advancing) / max(1, declining)

        # Breadth regime determination based on SMA50 participation
        breadth_pct_50 = float(above_sma50) / covered_count
        breadth_regime = "neutral"
        if breadth_pct_50 > 0.70:
            breadth_regime = "strong"
        elif breadth_pct_50 < 0.30:
            breadth_regime = "weak"

        return {
            "universe": universe,
            "status": "active",
            "coverage": {
                "total_universe_size": total_universe,
                "active_coverage_size": covered_count,
                "coverage_ratio": round(coverage_ratio, 2),
                "missing_symbols": missing_symbols
            },
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_decline_ratio": round(ad_ratio, 2),
            "breadth_regime": breadth_regime,
            "participation": {
                "pct_above_sma20": round(float(above_sma20) / covered_count * 100, 2),
                "pct_above_sma50": round(float(above_sma50) / covered_count * 100, 2),
                "pct_above_sma200": round(float(above_sma200) / covered_count * 100, 2)
            },
            "new_highs_count": new_highs,
            "new_lows_count": new_lows
        }

    def calculate_sector_performance(self, as_of: datetime) -> List[Dict[str, Any]]:
        """
        Calculates sector relative returns, momentum, and constructs the sector leaderboard.
        """
        companies = Company.objects.filter(is_active=True).exclude(sector__in=[None, "Unknown", "Index", "Global Index", "Currency", "Commodity", "Macro"])
        sectors = set(companies.values_list('sector', flat=True))
        
        # Load Nifty return for relative strength comparison
        nifty_inst = Instrument.objects.filter(symbol="^NSEI", is_active=True).first()
        nifty_ret = 0.0
        if nifty_inst:
            nifty_features = get_indicators_pit(nifty_inst, as_of)
            if nifty_features and "daily_return" in nifty_features:
                nifty_ret = nifty_features["daily_return"]

        sector_results = []
        for sec in sectors:
            sec_comps = companies.filter(sector=sec)
            sec_insts = Instrument.objects.filter(company__in=sec_comps, instrument_type="EQUITY", is_active=True)
            
            returns = []
            rsis = []
            vols = []
            
            for inst in sec_insts:
                features = get_indicators_pit(inst, as_of)
                if features:
                    if features.get("daily_return") is not None:
                        returns.append(features["daily_return"])
                    if features.get("rsi14") is not None:
                        rsis.append(features["rsi14"])
                    if features.get("vol20") is not None:
                        vols.append(features["vol20"])
            
            if not returns:
                continue
                
            avg_return = float(np.mean(returns))
            avg_rsi = float(np.mean(rsis)) if rsis else None
            avg_vol = float(np.mean(vols)) if vols else None
            rel_return = avg_return - nifty_ret

            # Fetch 5 days ago returns for improving/deteriorating check
            t_5_days_ago = as_of - timedelta(days=7)
            returns_5d = []
            for inst in sec_insts:
                features_5d = get_indicators_pit(inst, t_5_days_ago)
                if features_5d and features_5d.get("daily_return") is not None:
                    returns_5d.append(features_5d["daily_return"])
            
            avg_return_5d = float(np.mean(returns_5d)) if returns_5d else 0.0
            momentum_state = "stable"
            if avg_return - avg_return_5d > 0.015:
                momentum_state = "improving"
            elif avg_return - avg_return_5d < -0.015:
                momentum_state = "deteriorating"

            sector_results.append({
                "sector": sec,
                "average_return": round(avg_return * 100, 4),  # percentage
                "relative_return_vs_nifty": round(rel_return * 100, 4),
                "average_rsi": round(avg_rsi, 2) if avg_rsi else None,
                "average_volatility": round(avg_vol, 6) if avg_vol else None,
                "momentum_state": momentum_state
            })

        # Sort leaderboard by average return descending
        sector_results.sort(key=lambda s: s["average_return"], reverse=True)
        
        # Assign rankings and classify strongest/weakest
        n_sectors = len(sector_results)
        for rank, sec in enumerate(sector_results, 1):
            sec["rank"] = rank
            if rank <= max(1, n_sectors // 4):
                sec["tier"] = "strongest"
            elif rank > n_sectors - max(1, n_sectors // 4):
                sec["tier"] = "weakest"
            else:
                sec["tier"] = "neutral"

        return sector_results

    def retrieve_global_cues(self, as_of: datetime) -> Dict[str, Any]:
        """
        Retrieves global assets last close, day change, and determines staleness.
        """
        global_tickers = {
            "^GSPC": "S&P 500",
            "^IXIC": "Nasdaq",
            "^DJI": "Dow Jones",
            "^VIX": "CBOE VIX",
            "USDINR=X": "USD/INR Rate",
            "CL=F": "Crude Oil Futures",
            "GC=F": "Gold Futures",
            "^TNX": "US 10-Yr Treasury Yield"
        }

        results = {}
        for ticker, name in global_tickers.items():
            inst = Instrument.objects.filter(symbol=ticker, is_active=True).first()
            if not inst:
                results[ticker] = {"name": name, "status": "missing_instrument"}
                continue

            features = get_indicators_pit(inst, as_of)
            if not features or "close" not in features:
                results[ticker] = {"name": name, "status": "no_data"}
                continue

            close = features["close"]
            ret = features["daily_return"]
            timestamps = features["bar_timestamps"]
            last_timestamp = timestamps[-1] if timestamps else None

            # Determine staleness (older than 48 hours relative to as_of)
            is_stale = False
            if last_timestamp:
                is_stale = (as_of - last_timestamp) > timedelta(hours=48)

            results[ticker] = {
                "name": name,
                "status": "active",
                "close": round(close, 4) if ticker == "USDINR=X" else round(close, 2),
                "daily_change_percent": round(ret * 100, 2) if ret is not None else 0.0,
                "last_timestamp": last_timestamp.isoformat() if last_timestamp else None,
                "stale": is_stale
            }

        return results

    def calculate_cross_market_features(self, as_of: datetime) -> Dict[str, Any]:
        """
        Calculates Pearson rolling correlations between Nifty 50 returns and global cues.
        """
        nifty = Instrument.objects.filter(symbol="^NSEI", is_active=True).first()
        if not nifty:
            return {"status": "error", "error": "Nifty 50 instrument not found."}

        nifty_feat = get_indicators_pit(nifty, as_of)
        if not nifty_feat or "daily_returns_map" not in nifty_feat:
            return {"status": "error", "error": "Nifty 50 daily returns unavailable."}

        nifty_returns = nifty_feat["daily_returns_map"]
        correlations = {}

        global_targets = ["^GSPC", "USDINR=X", "CL=F"]
        for target in global_targets:
            t_inst = Instrument.objects.filter(symbol=target, is_active=True).first()
            if not t_inst:
                correlations[target] = "missing_instrument"
                continue

            t_feat = get_indicators_pit(t_inst, as_of)
            if not t_feat or "daily_returns_map" not in t_feat:
                correlations[target] = "no_data"
                continue

            t_returns = t_feat["daily_returns_map"]
            
            # Align by matching dates in the last 30 calendar days
            aligned_nifty = []
            aligned_target = []
            for d in sorted(nifty_returns.keys(), reverse=True)[:25]:  # Look back 25 trading days
                if d in t_returns:
                    aligned_nifty.append(nifty_returns[d])
                    aligned_target.append(t_returns[d])

            if len(aligned_nifty) < 15:
                correlations[target] = "insufficient_data"
                continue

            # Calculate Pearson correlation
            corr_matrix = np.corrcoef(aligned_nifty, aligned_target)
            coeff = corr_matrix[0, 1]
            correlations[target] = round(float(coeff), 4) if not np.isnan(coeff) else "error"

        return {
            "rolling_20d_correlations": correlations,
            "disclaimer": "rolling correlations represent statistical relationships only and do not imply causation."
        }

    def retrieve_macro_events(self, as_of: datetime) -> List[Dict[str, Any]]:
        """
        Retrieves economic disclosures/news relating to RBI, Fed, inflation near as_of.
        """
        # Look for news or disclosures matching macro keywords
        keywords = ["RBI", "FOMC", "inflation", "CPI", "GDP", "interest rate", "Federal Reserve"]
        
        news_q_obj = Q()
        for kw in keywords:
            news_q_obj |= Q(headline__icontains=kw) | Q(summary__icontains=kw)

        disc_q_obj = Q()
        for kw in keywords:
            disc_q_obj |= Q(headline__icontains=kw)

        events = list(NewsItem.objects.filter(
            news_q_obj,
            published_at__lte=as_of
        ).order_by('-published_at')[:3])

        disclosures = list(CorporateDisclosure.objects.filter(
            disc_q_obj,
            published_at__lte=as_of
        ).order_by('-published_at')[:3])

        combined = []
        for ev in events:
            combined.append({
                "type": "news",
                "headline": ev.headline,
                "published_at": ev.published_at.isoformat(),
                "source": ev.source
            })
        for disc in disclosures:
            combined.append({
                "type": "disclosure",
                "headline": disc.headline,
                "published_at": disc.published_at.isoformat(),
                "source": disc.source
            })

        combined.sort(key=lambda x: x["published_at"], reverse=True)
        return combined[:5]

    def get_market_context(self, as_of: Any = None, universe: str = "NIFTY50") -> Dict[str, Any]:
        """
        Aggregates all context components into a structured document.
        """
        dt_as_of = self._parse_as_of(as_of)
        
        # Calculate Regimes
        nifty_regime = self.calculate_market_regime("^NSEI", dt_as_of)
        bank_regime = self.calculate_market_regime("^NSEBANK", dt_as_of)
        
        # Calculate Breadth
        breadth = self.calculate_market_breadth(universe, dt_as_of)
        
        # Calculate Sectors
        sectors = self.calculate_sector_performance(dt_as_of)
        
        # Retrieve Global Cues
        global_cues = self.retrieve_global_cues(dt_as_of)
        
        # Calculate Cross-market
        cross_market = self.calculate_cross_market_features(dt_as_of)
        
        # Macro Events
        macro = self.retrieve_macro_events(dt_as_of)

        # Evaluate Data Quality & Coverage
        missing_keys = []
        stale_keys = []
        for k, v in global_cues.items():
            if v.get("status") != "active":
                missing_keys.append(k)
            elif v.get("stale"):
                stale_keys.append(k)
                
        for index in ("^NSEI", "^NSEBANK"):
            if index == "^NSEI" and nifty_regime.get("status") != "active":
                missing_keys.append(index)
            if index == "^NSEBANK" and bank_regime.get("status") != "active":
                missing_keys.append(index)

        quality_score = 100
        if missing_keys:
            quality_score -= len(missing_keys) * 15
        if stale_keys:
            quality_score -= len(stale_keys) * 5
            
        data_quality = {
            "score": max(0, quality_score),
            "missing_keys": missing_keys,
            "stale_keys": stale_keys,
            "notes": "Quality score represents overall availability of benchmarks and global indicators."
        }

        return {
            "as_of": dt_as_of.isoformat(),
            "universe": universe,
            "index_regimes": {
                "^NSEI": nifty_regime,
                "^NSEBANK": bank_regime
            },
            "breadth": breadth,
            "sector_rankings": sectors,
            "global_cues": global_cues,
            "cross_market_features": cross_market,
            "macro_events": macro,
            "data_quality": data_quality
        }

    def save_market_context_snapshot(self, context: Dict[str, Any]) -> MarketContextSnapshot:
        """
        Saves a MarketContextSnapshot to the database.
        """
        as_of = self._parse_as_of(context["as_of"])
        universe = context["universe"]
        
        # Check if snapshot already exists to overwrite cleanly
        MarketContextSnapshot.objects.filter(as_of=as_of, universe=universe).delete()
        
        snapshot = MarketContextSnapshot.objects.create(
            as_of=as_of,
            universe=universe,
            calculations_version=1,
            index_regimes=context["index_regimes"],
            breadth=context["breadth"],
            sector_rankings=context["sector_rankings"],
            global_cues=context["global_cues"],
            cross_market_features=context["cross_market_features"],
            macro_events=context["macro_events"],
            data_quality=context["data_quality"]
        )
        return snapshot
