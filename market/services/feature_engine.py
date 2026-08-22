import logging
import numpy as np
import talib
from typing import Dict, Any, List, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from market.models import Instrument, OHLCVBar, TechnicalFeature

logger = logging.getLogger(__name__)

# Phase 7 Configuration specification mechanism
DEFAULT_INDICATOR_CONFIG = {
    "sma": [20, 50, 200],
    "ema": [20, 50, 200],
    "rsi": [14],
    "macd": [{"fast": 12, "slow": 26, "signal": 9}],
    "atr": [14],
    "volatility": [20],
    "volume_sma": [20],
    "rolling_high_low": [20]
}

class TechnicalFeatureEngine:
    """
    Derived-feature engine that executes TA-Lib and custom mathematical functions
    chronologically over historical OHLCVBar series, ensuring look-ahead safety
    and explicit warmup handling.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DEFAULT_INDICATOR_CONFIG

    def calculate_and_save_features(self, instrument: Instrument, timeframe: str = "1d") -> int:
        """
        Loads bars chronologically, computes technical indicators, and persists
        the derived features to the TechnicalFeature table.
        """
        # Load bars sorted chronologically (Look-ahead safety: calculations must run oldest to newest)
        bars = list(OHLCVBar.objects.filter(
            instrument=instrument,
            timeframe=timeframe
        ).order_by('timestamp'))
        
        n_bars = len(bars)
        if n_bars == 0:
            logger.warning(f"FeatureEngine: No bars found for {instrument.symbol} [{timeframe}]. Skipping features.")
            return 0
            
        # Convert bar fields to float64 numpy arrays for TA-Lib compatibility
        opens = np.array([float(b.open) for b in bars], dtype=np.float64)
        highs = np.array([float(b.high) for b in bars], dtype=np.float64)
        lows = np.array([float(b.low) for b in bars], dtype=np.float64)
        closes = np.array([float(b.close) for b in bars], dtype=np.float64)
        volumes = np.array([float(b.volume) for b in bars], dtype=np.float64)
        
        features_dict = {}
        
        # Calculate Trend Indicators
        for period in self.config.get("sma", []):
            key = f"SMA_{period}"
            param_key = f"period={period}"
            features_dict[(key, param_key)] = talib.SMA(closes, timeperiod=period)
            
        for period in self.config.get("ema", []):
            key = f"EMA_{period}"
            param_key = f"period={period}"
            features_dict[(key, param_key)] = talib.EMA(closes, timeperiod=period)
            
        # Calculate Momentum Indicators
        for period in self.config.get("rsi", []):
            key = f"RSI_{period}"
            param_key = f"period={period}"
            features_dict[(key, param_key)] = talib.RSI(closes, timeperiod=period)
            
        for params in self.config.get("macd", []):
            fast = params["fast"]
            slow = params["slow"]
            sig = params["signal"]
            param_key = f"fast={fast};slow={slow};signal={sig}"
            
            macd, macdsignal, macdhist = talib.MACD(
                closes,
                fastperiod=fast,
                slowperiod=slow,
                signalperiod=sig
            )
            features_dict[(f"MACD_line", param_key)] = macd
            features_dict[(f"MACD_signal", param_key)] = macdsignal
            features_dict[(f"MACD_hist", param_key)] = macdhist

        # Calculate Volatility Indicators
        for period in self.config.get("atr", []):
            key = f"ATR_{period}"
            param_key = f"period={period}"
            features_dict[(key, param_key)] = talib.ATR(highs, lows, closes, timeperiod=period)
            
        # Daily Return
        returns = np.zeros_like(closes)
        if n_bars > 1:
            returns[1:] = (closes[1:] - closes[:-1]) / closes[:-1]
        returns[0] = np.nan
        features_dict[("daily_return", "period=1")] = returns
        
        # Cumulative Return
        cum_returns = np.zeros_like(closes)
        if n_bars > 0:
            cum_returns = (closes - closes[0]) / closes[0]
        features_dict[("cumulative_return", "period=all")] = cum_returns
        
        # Volatility (Rolling Std Dev of daily returns)
        for period in self.config.get("volatility", []):
            vol = np.full_like(closes, np.nan)
            for i in range(period - 1, n_bars):
                window = returns[i - (period - 1): i + 1]
                valid_window = window[~np.isnan(window)]
                if len(valid_window) >= period:
                    vol[i] = np.std(valid_window, ddof=1)
            features_dict[(f"rolling_volatility_{period}", f"period={period}")] = vol

        # Volume Indicators
        for period in self.config.get("volume_sma", []):
            vol_sma = talib.SMA(volumes, timeperiod=period)
            features_dict[(f"volume_SMA_{period}", f"period={period}")] = vol_sma
            
            # Relative Volume
            rel_vol = np.full_like(volumes, np.nan)
            non_zero = (vol_sma > 0) & (~np.isnan(vol_sma))
            rel_vol[non_zero] = volumes[non_zero] / vol_sma[non_zero]
            features_dict[(f"relative_volume_{period}", f"period={period}")] = rel_vol

        # Rolling Highs / Lows and Distances
        for period in self.config.get("rolling_high_low", []):
            r_high = talib.MAX(closes, timeperiod=period)
            r_low = talib.MIN(closes, timeperiod=period)
            features_dict[(f"rolling_high_{period}", f"period={period}")] = r_high
            features_dict[(f"rolling_low_{period}", f"period={period}")] = r_low
            
            dist_high = np.full_like(closes, np.nan)
            valid_h = ~np.isnan(r_high)
            dist_high[valid_h] = closes[valid_h] - r_high[valid_h]
            features_dict[(f"distance_from_high_{period}", f"period={period}")] = dist_high
            
            dist_low = np.full_like(closes, np.nan)
            valid_l = ~np.isnan(r_low)
            dist_low[valid_l] = closes[valid_l] - r_low[valid_l]
            features_dict[(f"distance_from_low_{period}", f"period={period}")] = dist_low

        # Build records to persist
        features_to_create = []
        
        # We process each bar chronologically
        for i, bar in enumerate(bars):
            for (name, param_key), values_array in features_dict.items():
                val = values_array[i]
                
                # Warmup handling: if the value is NaN, we represent it as None
                decimal_val = None
                if not np.isnan(val) and not np.isinf(val):
                    decimal_val = Decimal(f"{val:.6f}")
                    
                features_to_create.append(TechnicalFeature(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=bar.timestamp,
                    name=name,
                    parameters={},  # Default empty dictionary, params tracked in param_key string
                    param_key=param_key,
                    value=decimal_val
                ))

        # Enforce persistence atomicity and idempotency
        with transaction.atomic():
            # Delete any existing features for this instrument and timeframe to overwrite cleanly
            TechnicalFeature.objects.filter(
                instrument=instrument,
                timeframe=timeframe
            ).delete()
            
            # Bulk create to avoid N+1 write operations
            if features_to_create:
                TechnicalFeature.objects.bulk_create(features_to_create, batch_size=1000)

        logger.info(f"FeatureEngine: calculated and persisted {len(features_to_create)} technical features for {instrument.symbol}.")
        return len(features_to_create)
