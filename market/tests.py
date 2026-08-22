from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import numpy as np
import requests

from market.models import Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature
from market.providers.yfinance import YFinanceMarketProvider
from market.normalizers.yfinance import YFinanceNormalizer
from market.services.market_service import MarketService
from market.services.feature_engine import TechnicalFeatureEngine
from market.exceptions import (
    ProviderConnectionError,
    RateLimitExceededError,
    SymbolNotFoundError,
    InvalidPayloadError,
    AuthenticationError
)
from llm.tools.registry import ToolRegistry
from llm.tools.executor import ToolExecutor
from llm.tools.implementations.market_tool import (
    GetStockSnapshotTool,
    GetHistoricalOHLCVTool,
    GetTechnicalFeaturesTool
)

# Standard mock response payload matching Yahoo Finance Chart API structure
MOCK_CHART_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "currency": "INR",
                    "symbol": "TCS.NS",
                    "exchangeName": "NSI",
                    "fullExchangeName": "NSE",
                    "instrumentType": "EQUITY",
                    "regularMarketTime": 1787305502,
                    "regularMarketPrice": 3400.0,
                    "regularMarketDayHigh": 3420.0,
                    "regularMarketDayLow": 3390.0,
                    "regularMarketVolume": 1000000,
                    "chartPreviousClose": 3380.0
                },
                "indicators": {
                    "quote": [
                        {
                            "open": [3395.0],
                            "high": [3420.0],
                            "low": [3390.0],
                            "close": [3400.0],
                            "volume": [1000000]
                        }
                    ]
                }
            }
        ],
        "error": None
    }
}

# 10 days of mock chart data for historical checks
MOCK_HIST_CHART_RESPONSE = {
    "chart": {
        "result": [
            {
                "meta": {
                    "currency": "INR",
                    "symbol": "INFY.NS",
                    "exchangeName": "NSI",
                    "fullExchangeName": "NSE",
                    "instrumentType": "EQUITY",
                    "regularMarketTime": 1787305500
                },
                "timestamp": [
                    1704067200, 1704153600, 1704240000, 1704326400, 1704412800,
                    1704499200, 1704585600, 1704672000, 1704758400, 1704844800
                ],
                "indicators": {
                    "quote": [
                        {
                            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
                            "high": [105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0],
                            "low": [98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
                            "close": [102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0],
                            "volume": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900]
                        }
                    ]
                }
            }
        ],
        "error": None
    }
}


class MarketSubsystemTests(TestCase):
    """
    Mandatory unit/integration tests verifying the Yahoo Finance provider,
    normalization logic, data quality filters, service idempotency, and tool execution.
    """

    @patch("requests.get")
    def test_provider_success_payload(self, mock_get):
        """Verifies YFinanceMarketProvider requests data correctly and returns dictionary."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_CHART_RESPONSE
        mock_get.return_value = mock_resp

        provider = YFinanceMarketProvider()
        data = provider.get_quote("TCS")
        
        self.assertIn("chart", data)
        self.assertEqual(data["chart"]["result"][0]["meta"]["symbol"], "TCS.NS")
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_provider_exceptions(self, mock_get):
        """Verifies provider status codes and network errors map to custom exceptions."""
        provider = YFinanceMarketProvider()

        # 1. Timeout -> ProviderConnectionError
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        with self.assertRaises(ProviderConnectionError):
            provider.get_quote("TCS")

        # Reset side_effect
        mock_get.side_effect = None

        # 2. 401 Unauthorized -> AuthenticationError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp
        with self.assertRaises(AuthenticationError):
            provider.get_quote("TCS")

        # 3. 429 Too Many Requests -> RateLimitExceededError
        mock_resp.status_code = 429
        with self.assertRaises(RateLimitExceededError):
            provider.get_quote("TCS")

        # 4. 404 Not Found -> SymbolNotFoundError
        mock_resp.status_code = 404
        with self.assertRaises(SymbolNotFoundError):
            provider.get_quote("TCS")

    def test_normalizer_success(self):
        """Verifies YFinanceNormalizer parses clean payloads into canonical Pydantic MarketQuotes."""
        normalizer = YFinanceNormalizer()
        
        curr_epoch = int(datetime.now(timezone.utc).timestamp())
        payload = dict(MOCK_CHART_RESPONSE)
        payload["chart"]["result"][0]["meta"]["regularMarketTime"] = curr_epoch
        
        quote = normalizer.normalize(payload)
        
        self.assertEqual(quote.symbol, "TCS")
        self.assertEqual(quote.exchange, "NSE")
        self.assertEqual(quote.price, Decimal("3400.0"))
        self.assertEqual(quote.open_price, Decimal("3395.0"))
        self.assertEqual(quote.high, Decimal("3420.0"))
        self.assertEqual(quote.low, Decimal("3390.0"))
        self.assertEqual(quote.volume, 1000000)
        self.assertEqual(quote.previous_close, Decimal("3380.0"))
        self.assertEqual(quote.change, Decimal("20.0"))
        self.assertEqual(quote.change_percent, Decimal("0.59"))

    def test_normalizer_data_quality_gates(self):
        """Verifies data quality validation filters raise ValueErrors for corrupt/invalid inputs."""
        normalizer = YFinanceNormalizer()
        curr_epoch = int(datetime.now(timezone.utc).timestamp())

        # helper function to generate test payloads
        def get_test_payload(price=3400.0, low=3390.0, high=3420.0, vol=1000000, market_time=curr_epoch):
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "TCS.NS",
                                "regularMarketPrice": price,
                                "regularMarketDayHigh": high,
                                "regularMarketDayLow": low,
                                "regularMarketVolume": vol,
                                "regularMarketTime": market_time
                            },
                            "indicators": {
                                "quote": [{"open": [3395.0], "high": [high], "low": [low], "close": [price], "volume": [vol]}]
                            }
                        }
                    ]
                }
            }

        # 1. Negative Price
        with self.assertRaises(ValueError):
            normalizer.normalize(get_test_payload(price=-10.0))

        # 2. Low > High
        with self.assertRaises(ValueError):
            normalizer.normalize(get_test_payload(low=3500.0, high=3400.0))

        # 3. Future timestamp (Clock skew > 5 mins)
        future_epoch = int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp())
        with self.assertRaises(ValueError):
            normalizer.normalize(get_test_payload(market_time=future_epoch))

        # 4. Stale observation (> 7 days)
        stale_epoch = int((datetime.now(timezone.utc) - timedelta(days=8)).timestamp())
        with self.assertRaises(ValueError):
            normalizer.normalize(get_test_payload(market_time=stale_epoch))

    @patch("requests.get")
    def test_service_persistence_and_idempotency(self, mock_get):
        """Verifies MarketService correctly upserts records and prevents duplicate snapshot creation."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        
        curr_epoch = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "INR",
                            "symbol": "INFY.NS",
                            "exchangeName": "NSI",
                            "fullExchangeName": "NSE",
                            "instrumentType": "EQUITY",
                            "regularMarketTime": curr_epoch,
                            "regularMarketPrice": 1500.0,
                            "regularMarketDayHigh": 1510.0,
                            "regularMarketDayLow": 1490.0,
                            "regularMarketVolume": 500000,
                            "chartPreviousClose": 1480.0
                        },
                        "indicators": {
                            "quote": [{"open": [1495.0], "high": [1510.0], "low": [1490.0], "close": [1500.0], "volume": [500000]}]
                        }
                    }
                ]
            }
        }
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        service = MarketService()
        
        # 1. First fetch: creates Company, Instrument, and Snapshot
        quote1 = service.fetch_and_save_quote("INFY")
        
        self.assertEqual(Company.objects.filter(short_name="INFY").count(), 1)
        self.assertEqual(Instrument.objects.filter(symbol="INFY").count(), 1)
        self.assertEqual(MarketSnapshot.objects.filter(instrument__symbol="INFY").count(), 1)

        # 2. Second fetch (same quote timestamp): should skip creating duplicate snapshot (idempotency check)
        quote2 = service.fetch_and_save_quote("INFY")
        
        self.assertEqual(MarketSnapshot.objects.filter(instrument__symbol="INFY").count(), 1)

    @patch("requests.get")
    def test_get_stock_snapshot_tool_flow(self, mock_get):
        """Verifies complete tool execution path (Registry -> Executor -> Tool -> Service -> persistence)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        curr_epoch = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "INR",
                            "symbol": "RELIANCE.NS",
                            "exchangeName": "NSI",
                            "fullExchangeName": "NSE",
                            "instrumentType": "EQUITY",
                            "regularMarketTime": curr_epoch,
                            "regularMarketPrice": 2500.0,
                            "regularMarketDayHigh": 2520.0,
                            "regularMarketDayLow": 2490.0,
                            "regularMarketVolume": 2000000,
                            "chartPreviousClose": 2480.0
                        },
                        "indicators": {
                            "quote": [{"open": [2495.0], "high": [2520.0], "low": [2490.0], "close": [2500.0], "volume": [2000000]}]
                        }
                    }
                ]
            }
        }
        mock_resp.json.return_value = payload
        mock_get.return_value = mock_resp

        registry = ToolRegistry()
        tool = GetStockSnapshotTool()
        registry.register(tool)
        executor = ToolExecutor(registry=registry)

        result = executor.execute("get_stock_snapshot", {"symbol": "RELIANCE"})
        
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "YFinanceMarketProvider")
        self.assertEqual(result.data["symbol"], "RELIANCE")
        self.assertEqual(result.data["price"], 2500.0)
        self.assertEqual(result.data["volume"], 2000000)
        
        self.assertEqual(MarketSnapshot.objects.filter(instrument__symbol="RELIANCE").count(), 1)


class QuantTechnicalSubsystemTests(TestCase):
    """
    Subsystem tests checking historical OHLCV bar processing, validation gates,
    TA-Lib feature engine calculations, look-ahead prevention, and warmup boundaries.
    """

    @patch("requests.get")
    def test_historical_ohlcv_ingestion(self, mock_get):
        """Verifies historical ingestion saves correct OHLCVBars and prevents duplicates (idempotency)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_HIST_CHART_RESPONSE
        mock_get.return_value = mock_resp

        service = MarketService()
        
        # 1. Ingest historical bars
        bars = service.fetch_and_save_historical_ohlcv("INFY")
        
        self.assertEqual(len(bars), 10)
        self.assertEqual(OHLCVBar.objects.filter(instrument__symbol="INFY").count(), 10)
        
        # Verify first bar values
        first_bar = OHLCVBar.objects.filter(instrument__symbol="INFY").order_by('timestamp').first()
        self.assertEqual(first_bar.open, Decimal("100.00"))
        self.assertEqual(first_bar.close, Decimal("102.00"))
        self.assertEqual(first_bar.volume, 1000)
        
        # 2. Run ingestion again: must skip inserting duplicate bars to maintain idempotency
        bars_retry = service.fetch_and_save_historical_ohlcv("INFY")
        self.assertEqual(OHLCVBar.objects.filter(instrument__symbol="INFY").count(), 10)

    @patch("requests.get")
    def test_historical_validation_gates(self, mock_get):
        """Verifies invalid OHLC ranges, negative prices, and negative volumes raise ValueErrors in historical ingestion."""
        service = MarketService()
        
        # Helper function to generate mock payload with bad values
        def get_bad_payload(open_list, high_list, low_list, close_list, vol_list):
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "symbol": "INFY.NS",
                                "fullExchangeName": "NSE",
                                "regularMarketTime": 1704067200
                            },
                            "timestamp": [1704067200],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": open_list,
                                        "high": high_list,
                                        "low": low_list,
                                        "close": close_list,
                                        "volume": vol_list
                                    }
                                ]
                            }
                        }
                    ]
                }
            }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        # 1. Low > High
        mock_resp.json.return_value = get_bad_payload([100], [105], [110], [102], [1000])
        with self.assertRaises(ValueError):
            service.fetch_and_save_historical_ohlcv("INFY")

        # 2. Open > High
        mock_resp.json.return_value = get_bad_payload([115], [110], [100], [102], [1000])
        with self.assertRaises(ValueError):
            service.fetch_and_save_historical_ohlcv("INFY")

        # 3. Negative volume
        mock_resp.json.return_value = get_bad_payload([100], [105], [95], [102], [-100])
        with self.assertRaises(ValueError):
            service.fetch_and_save_historical_ohlcv("INFY")

    @patch("requests.get")
    def test_feature_calculations_and_warmup(self, mock_get):
        """Verifies TA-Lib and custom derived indicators are calculated and warmup limits are set to None/Null."""
        # Setup 21 bars to verify simple SMA_20 calculation and its warmup
        timestamps = [1704067200 + i * 86400 for i in range(25)]
        closes = [100.0 + i for i in range(25)]
        opens = [99.0 + i for i in range(25)]
        highs = [102.0 + i for i in range(25)]
        lows = [98.0 + i for i in range(25)]
        volumes = [1000 + i for i in range(25)]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "INR",
                            "symbol": "RELIANCE.NS",
                            "exchangeName": "NSI",
                            "fullExchangeName": "NSE",
                            "instrumentType": "EQUITY",
                            "regularMarketTime": timestamps[-1]
                        },
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [{"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}]
                        }
                    }
                ],
                "error": None
            }
        }
        mock_get.return_value = mock_resp

        service = MarketService()
        
        # Ingest bars
        service.fetch_and_save_historical_ohlcv("RELIANCE")
        
        # Calculate derived indicators
        count = service.calculate_features("RELIANCE")
        self.assertGreater(count, 0)
        
        # Verify SMA_20 warmup logic: First 19 bars should have value = None due to warmup constraints
        features = TechnicalFeature.objects.filter(
            instrument__symbol="RELIANCE",
            name="SMA_20"
        ).order_by('timestamp')
        
        self.assertEqual(features.count(), 25)
        
        # First bar must be None/Null (warmup not satisfied)
        self.assertIsNone(features[0].value)
        self.assertIsNone(features[18].value)
        
        # Bar 20 (index 19) must be populated (warmup satisfied)
        self.assertIsNotNone(features[19].value)
        self.assertEqual(features[19].value, Decimal("109.500000")) # Average of 100..119 is 109.5

    @patch("requests.get")
    def test_look_ahead_safety_and_determinism(self, mock_get):
        """Verifies feature calculations are look-ahead safe and deterministic."""
        # 1. Look-ahead safety check:
        # If we calculate indicators for a historical series, the value at timestamp T
        # must remain identical whether we calculate it on the full list OR on a truncated list ending at T.
        timestamps = [1704067200 + i * 86400 for i in range(25)]
        closes = [100.0 + i for i in range(25)]
        opens = [99.0 + i for i in range(25)]
        highs = [102.0 + i for i in range(25)]
        lows = [98.0 + i for i in range(25)]
        volumes = [1000 + i for i in range(25)]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "RELIANCE.NS",
                            "fullExchangeName": "NSE",
                            "regularMarketTime": timestamps[-1]
                        },
                        "timestamp": timestamps,
                        "indicators": {
                            "quote": [{"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}]
                        }
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp

        service = MarketService()
        
        # Ingest full history and calculate features
        service.fetch_and_save_historical_ohlcv("RELIANCE")
        service.calculate_features("RELIANCE")
        
        # Retrieve value at index 20 (timestamp 1704067200 + 20*86400)
        target_timestamp = datetime.fromtimestamp(timestamps[20], tz=timezone.utc)
        val_full = TechnicalFeature.objects.get(
            instrument__symbol="RELIANCE",
            name="RSI_14",
            timestamp=target_timestamp
        ).value

        # Truncate bars in database (simulate database state at timestamp T)
        OHLCVBar.objects.filter(instrument__symbol="RELIANCE", timestamp__gt=target_timestamp).delete()
        
        # Recalculate indicators on truncated series
        service.calculate_features("RELIANCE")
        
        val_truncated = TechnicalFeature.objects.get(
            instrument__symbol="RELIANCE",
            name="RSI_14",
            timestamp=target_timestamp
        ).value
        
        # The values must be IDENTICAL (proof of look-ahead safety)
        self.assertEqual(val_full, val_truncated)

        # 2. Determinism check: Repeated calculation produces identical output values
        service.calculate_features("RELIANCE")
        val_repeated = TechnicalFeature.objects.get(
            instrument__symbol="RELIANCE",
            name="RSI_14",
            timestamp=target_timestamp
        ).value
        self.assertEqual(val_truncated, val_repeated)

    @patch("requests.get")
    def test_historical_tools_layer(self, mock_get):
        """Verifies get_historical_ohlcv and get_technical_features tools execute correctly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_HIST_CHART_RESPONSE
        mock_get.return_value = mock_resp

        # Initialize tools
        registry = ToolRegistry()
        ohlcv_tool = GetHistoricalOHLCVTool()
        features_tool = GetTechnicalFeaturesTool()
        registry.register(ohlcv_tool)
        registry.register(features_tool)
        executor = ToolExecutor(registry=registry)

        # 1. Execute get_historical_ohlcv tool
        result_ohlcv = executor.execute("get_historical_ohlcv", {"symbol": "INFY", "limit": 5})
        self.assertTrue(result_ohlcv.success)
        self.assertEqual(len(result_ohlcv.data), 5)
        self.assertIn("close", result_ohlcv.data[0])

        # 2. Execute get_technical_features tool
        # (It will calculate features dynamically because INFY has bars but no features stored yet)
        result_feat = executor.execute("get_technical_features", {"symbol": "INFY", "name": "daily_return"})
        self.assertTrue(result_feat.success)
        self.assertGreater(len(result_feat.data), 0)
        self.assertEqual(result_feat.data[0]["name"], "daily_return")
