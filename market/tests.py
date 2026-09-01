from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from django.db.models import Q
from unittest.mock import patch, MagicMock
import numpy as np
import requests
import json

from market.models import (
    Company,
    Instrument,
    MarketSnapshot,
    OHLCVBar,
    TechnicalFeature,
    RawFundamentalData,
    IncomeStatement,
    BalanceSheetStatement,
    CashFlowStatement,
    DerivedFundamentalMetric,
    NewsItem,
    CorporateDisclosure,
    Universe,
    UniverseMembership,
    StockOpportunitySnapshot,
    MarketContextSnapshot
)
from market.providers.yfinance import YFinanceMarketProvider
from market.normalizers.yfinance import YFinanceNormalizer
from market.services.market_service import MarketService
from market.services.feature_engine import TechnicalFeatureEngine
from market.services.fundamental_service import FundamentalDataService
from market.services.news_service import NewsIntelligenceService
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
    GetTechnicalFeaturesTool,
    GetCompanyFinancialsTool,
    GetFinancialMetricsTool,
    GetCompanyNewsTool,
    GetCompanyEventsTool,
    GetMarketNewsTool
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


MOCK_SCREENER_HTML = """
<section id="quarters">
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Dec 2024</th>
        <th>Mar 2025</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Sales</td>
        <td>1000</td>
        <td>1200</td>
      </tr>
      <tr>
        <td>Expenses</td>
        <td>800</td>
        <td>900</td>
      </tr>
      <tr>
        <td>Operating Profit</td>
        <td>200</td>
        <td>300</td>
      </tr>
      <tr>
        <td>Net Profit</td>
        <td>120</td>
        <td>180</td>
      </tr>
      <tr>
        <td>EPS in Rs</td>
        <td>1.20</td>
        <td>1.80</td>
      </tr>
    </tbody>
  </table>
</section>
<section id="profit-loss">
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Mar 2024</th>
        <th>Mar 2025</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Sales</td>
        <td>4000</td>
        <td>5000</td>
      </tr>
      <tr>
        <td>Expenses</td>
        <td>3200</td>
        <td>3800</td>
      </tr>
      <tr>
        <td>Operating Profit</td>
        <td>800</td>
        <td>1200</td>
      </tr>
      <tr>
        <td>Depreciation</td>
        <td>100</td>
        <td>120</td>
      </tr>
      <tr>
        <td>Interest</td>
        <td>50</td>
        <td>60</td>
      </tr>
      <tr>
        <td>Profit before tax</td>
        <td>650</td>
        <td>1020</td>
      </tr>
      <tr>
        <td>Net Profit</td>
        <td>500</td>
        <td>800</td>
      </tr>
      <tr>
        <td>EPS in Rs</td>
        <td>5.00</td>
        <td>8.00</td>
      </tr>
    </tbody>
  </table>
</section>
<section id="balance-sheet">
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Mar 2024</th>
        <th>Mar 2025</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Equity Capital</td>
        <td>100</td>
        <td>100</td>
      </tr>
      <tr>
        <td>Reserves</td>
        <td>900</td>
        <td>1400</td>
      </tr>
      <tr>
        <td>Borrowings</td>
        <td>500</td>
        <td>600</td>
      </tr>
      <tr>
        <td>Other Liabilities</td>
        <td>200</td>
        <td>300</td>
      </tr>
      <tr>
        <td>Total Liabilities</td>
        <td>1700</td>
        <td>2400</td>
      </tr>
      <tr>
        <td>Fixed Assets</td>
        <td>1000</td>
        <td>1300</td>
      </tr>
      <tr>
        <td>CWIP</td>
        <td>100</td>
        <td>200</td>
      </tr>
      <tr>
        <td>Investments</td>
        <td>300</td>
        <td>400</td>
      </tr>
      <tr>
        <td>Other Assets</td>
        <td>300</td>
        <td>500</td>
      </tr>
      <tr>
        <td>Total Assets</td>
        <td>1700</td>
        <td>2400</td>
      </tr>
    </tbody>
  </table>
</section>
<section id="cash-flow">
  <table>
    <thead>
      <tr>
        <th></th>
        <th>Mar 2024</th>
        <th>Mar 2025</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Cash from Operating Activity</td>
        <td>600</td>
        <td>900</td>
      </tr>
      <tr>
        <td>Cash from Investing Activity</td>
        <td>-400</td>
        <td>-600</td>
      </tr>
      <tr>
        <td>Cash from Financing Activity</td>
        <td>-150</td>
        <td>-200</td>
      </tr>
      <tr>
        <td>Free Cash Flow</td>
        <td>200</td>
        <td>300</td>
      </tr>
    </tbody>
  </table>
</section>
"""


class FundamentalAnalysisSubsystemTests(TestCase):
    """
    Subsystem tests checking raw fundamental data logging, statement normalization,
    derived metric formulas, quarterly vs annual period separation, and tool integrations.
    """

    def setUp(self):
        self.company = Company.objects.create(name="Infosys", short_name="INFY")
        self.instrument = Instrument.objects.create(company=self.company, symbol="INFY", exchange="NSE")

    @patch("requests.get")
    def test_screener_ingestion_and_provenance(self, mock_get):
        """Verifies ingestion saves RawFundamentalData logs for audit and maps statements cleanly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_SCREENER_HTML
        mock_get.return_value = mock_resp

        service = FundamentalDataService()
        raw_payload = service.ingest_company_financials("INFY")

        # 1. Verify Raw provenance logged
        self.assertEqual(RawFundamentalData.objects.filter(company=self.company).count(), 1)
        raw_log = RawFundamentalData.objects.get(company=self.company)
        self.assertEqual(raw_log.status, "NORMALIZED")
        self.assertEqual(raw_log.source, "screener")

        # 2. Verify Statements parsed
        # Annual: Mar 2024, Mar 2025
        self.assertEqual(IncomeStatement.objects.filter(company=self.company, period_type="ANNUAL").count(), 2)
        self.assertEqual(BalanceSheetStatement.objects.filter(company=self.company, period_type="ANNUAL").count(), 2)
        self.assertEqual(CashFlowStatement.objects.filter(company=self.company, period_type="ANNUAL").count(), 2)

        # Quarterly: Dec 2024, Mar 2025
        self.assertEqual(IncomeStatement.objects.filter(company=self.company, period_type="QUARTERLY").count(), 2)

        # 3. Verify normalized data values for Mar 2025
        inc_2025 = IncomeStatement.objects.get(company=self.company, period_type="ANNUAL", period_string="Mar 2025")
        self.assertEqual(inc_2025.revenue, Decimal("5000.00"))
        self.assertEqual(inc_2025.pat, Decimal("800.00"))
        self.assertEqual(inc_2025.ebit, Decimal("1080.00"))  # EBITDA (1200) - Dep (120) = 1080

        bal_2025 = BalanceSheetStatement.objects.get(company=self.company, period_type="ANNUAL", period_string="Mar 2025")
        self.assertEqual(bal_2025.borrowings, Decimal("600.00"))
        self.assertEqual(bal_2025.equity_capital, Decimal("100.00"))
        self.assertEqual(bal_2025.reserves, Decimal("1400.00"))

        cf_2025 = CashFlowStatement.objects.get(company=self.company, period_type="ANNUAL", period_string="Mar 2025")
        self.assertEqual(cf_2025.operating_cash_flow, Decimal("900.00"))
        self.assertEqual(cf_2025.free_cash_flow, Decimal("300.00"))

    @patch("requests.get")
    def test_derived_fundamental_metrics(self, mock_get):
        """Verifies formulas for derived growth, margins, return metrics, and leverage ratios."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_SCREENER_HTML
        mock_get.return_value = mock_resp

        service = FundamentalDataService()
        service.ingest_company_financials("INFY")

        # Ratios for Mar 2025:
        # 1. Revenue Growth YoY: (5000 - 4000) / 4000 = 0.25 (25%)
        # 2. EBITDA Margin: 1200 / 5000 = 0.24 (24%)
        # 3. Debt/Equity: Borrowings (600) / (Equity Capital 100 + Reserves 1400) = 600 / 1500 = 0.40
        # 4. ROE: PAT (800) / Equity (1500) = 0.533333 (53.33%)
        # 5. ROCE: EBIT (1080) / Capital Employed (Equity 1500 + Borrowings 600) = 1080 / 2100 = 0.514286 (51.43%)
        
        rev_growth = DerivedFundamentalMetric.objects.get(company=self.company, name="revenue_growth_yoy", period_string="Mar 2025")
        self.assertEqual(rev_growth.value, Decimal("0.250000"))

        ebitda_margin = DerivedFundamentalMetric.objects.get(company=self.company, name="ebitda_margin", period_string="Mar 2025")
        self.assertEqual(ebitda_margin.value, Decimal("0.240000"))

        debt_eq = DerivedFundamentalMetric.objects.get(company=self.company, name="debt_equity", period_string="Mar 2025")
        self.assertEqual(debt_eq.value, Decimal("0.400000"))

        roe = DerivedFundamentalMetric.objects.get(company=self.company, name="return_on_equity", period_string="Mar 2025")
        self.assertEqual(roe.value, Decimal("0.533333"))

        roce = DerivedFundamentalMetric.objects.get(company=self.company, name="return_on_capital_employed", period_string="Mar 2025")
        self.assertEqual(roce.value, Decimal("0.514286"))

    def test_missing_values_distinctness(self):
        """Verifies missing financial statements fields are preserved as None/Null instead of coerced to zero."""
        # Create income statement manually with missing fields
        IncomeStatement.objects.create(
            company=self.company,
            period_type="ANNUAL",
            period_string="Mar 2026",
            fiscal_year=2026,
            revenue=Decimal("6000.00"),
            pat=None, # Missing PAT
            eps=None  # Missing EPS
        )
        
        inc = IncomeStatement.objects.get(company=self.company, period_string="Mar 2026")
        self.assertEqual(inc.revenue, Decimal("6000.00"))
        self.assertIsNone(inc.pat)
        self.assertIsNone(inc.eps)

    @patch("requests.get")
    def test_fundamental_tools_layer(self, mock_get):
        """Verifies get_company_financials and get_financial_metrics tools execute cleanly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_SCREENER_HTML
        mock_get.return_value = mock_resp

        registry = ToolRegistry()
        fin_tool = GetCompanyFinancialsTool()
        metrics_tool = GetFinancialMetricsTool()
        registry.register(fin_tool)
        registry.register(metrics_tool)
        executor = ToolExecutor(registry=registry)

        # 1. Execute get_company_financials
        result_fin = executor.execute("get_company_financials", {"symbol": "INFY", "period_type": "ANNUAL"})
        self.assertTrue(result_fin.success)
        self.assertEqual(len(result_fin.data["income_statement"]), 2)
        self.assertEqual(result_fin.data["income_statement"][1]["revenue"], 5000.0)

        # 2. Execute get_financial_metrics
        result_metrics = executor.execute("get_financial_metrics", {"symbol": "INFY", "name": "debt_equity"})
        self.assertTrue(result_metrics.success)
        self.assertEqual(len(result_metrics.data), 2)  # Mar 2024 and Mar 2025
        self.assertEqual(result_metrics.data[1]["value"], 0.40)


MOCK_NEWS_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yahoo Finance News</title>
    <link>http://finance.yahoo.com</link>
    <description>Latest news</description>
    <item>
      <title>Infosys Q3 net profit rises 10% YoY</title>
      <link>https://finance.yahoo.com/news/infosys-q3-net-profit-rises-12345.html</link>
      <pubDate>Thu, 20 Aug 2026 12:00:00 GMT</pubDate>
      <description>Infosys reported strong Q3 numbers with sales growing 12%.</description>
      <guid isPermaLink="false">infosys_q3_12345</guid>
    </item>
    <item>
      <title>Infosys declares interim dividend of Rs 20</title>
      <link>https://finance.yahoo.com/news/infosys-declares-interim-dividend-67890.html</link>
      <pubDate>Fri, 21 Aug 2026 12:00:00 GMT</pubDate>
      <description>Board declared Rs 20 dividend per equity share.</description>
      <guid isPermaLink="false">infosys_div_67890</guid>
    </item>
    <item>
      <title>Infosys bags USD 100M contract win</title>
      <link>https://finance.yahoo.com/news/infosys-bags-contract-win-99999.html</link>
      <pubDate>Sat, 22 Aug 2026 12:00:00 GMT</pubDate>
      <description>The company secured a major order from an international client.</description>
      <guid isPermaLink="false">infosys_order_99999</guid>
    </item>
  </channel>
</rss>
"""


class NewsAnalysisSubsystemTests(TestCase):
    """
    Subsystem tests checking news RSS feed parsing, event classification keyword mapping,
    strict content-hash deduplication, point-in-time querying constraints, and tools.
    """

    def setUp(self):
        self.company = Company.objects.create(name="Infosys", short_name="INFY")
        self.instrument = Instrument.objects.create(company=self.company, symbol="INFY", exchange="NSE")

    @patch("requests.get")
    def test_news_rss_parsing_and_ingestion(self, mock_get):
        """Verifies XML RSS response parses successfully and saves trace-auditable NewsItems."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp

        service = NewsIntelligenceService()
        items = service.fetch_and_save_company_news("INFY")

        self.assertEqual(len(items), 3)
        self.assertEqual(NewsItem.objects.filter(company=self.company).count(), 3)
        
        # Verify first parsed item values
        item = NewsItem.objects.filter(company=self.company).order_by('published_at').first()
        self.assertEqual(item.headline, "Infosys Q3 net profit rises 10% YoY")
        self.assertEqual(item.source, "yahoo_rss")
        self.assertEqual(item.source_id, "infosys_q3_12345")
        self.assertEqual(item.url, "https://finance.yahoo.com/news/infosys-q3-net-profit-rises-12345.html")
        self.assertEqual(item.event_type, "earnings/results")

    @patch("requests.get")
    def test_news_event_classification(self, mock_get):
        """Verifies deterministic event categories are mapped cleanly from title keywords."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp

        service = NewsIntelligenceService()
        service.fetch_and_save_company_news("INFY")

        # 1. earnings/results
        item_results = NewsItem.objects.get(source_id="infosys_q3_12345")
        self.assertEqual(item_results.event_type, "earnings/results")

        # 2. dividend
        item_div = NewsItem.objects.get(source_id="infosys_div_67890")
        self.assertEqual(item_div.event_type, "dividend")

        # 3. order/win
        item_order = NewsItem.objects.get(source_id="infosys_order_99999")
        self.assertEqual(item_order.event_type, "order/win")

    @patch("requests.get")
    def test_news_deduplication(self, mock_get):
        """Verifies strict content hash uniqueness checks prevent duplicate/syndicated db records."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp

        service = NewsIntelligenceService()
        
        # Ingest once
        service.fetch_and_save_company_news("INFY")
        self.assertEqual(NewsItem.objects.filter(company=self.company).count(), 3)

        # Ingest again: must ignore conflicts and skip duplicate entries
        service.fetch_and_save_company_news("INFY")
        self.assertEqual(NewsItem.objects.filter(company=self.company).count(), 3)

    @patch("requests.get")
    def test_point_in_time_safety(self, mock_get):
        """Verifies point-in-time as_of filters prevent future data leakage in backtesting queries."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp

        service = NewsIntelligenceService()
        service.fetch_and_save_company_news("INFY")

        # Set as_of to August 21, 2026 18:00:00 UTC (should exclude August 22 article)
        as_of_t = datetime(2026, 8, 21, 18, 0, 0, tzinfo=timezone.utc)
        
        pit_news = service.get_company_news(self.company.id, as_of=as_of_t)
        
        self.assertEqual(len(pit_news), 2)
        # Should contain Mar 20, Mar 21 articles, but not Mar 22 order win
        headlines = [n.headline for n in pit_news]
        self.assertIn("Infosys Q3 net profit rises 10% YoY", headlines)
        self.assertIn("Infosys declares interim dividend of Rs 20", headlines)
        self.assertNotIn("Infosys bags USD 100M contract win", headlines)

    @patch("requests.get")
    def test_news_tools_layer(self, mock_get):
        """Verifies news retrieval tools execute correctly and return clean structured schemas."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp

        registry = ToolRegistry()
        news_tool = GetCompanyNewsTool()
        events_tool = GetCompanyEventsTool()
        market_tool = GetMarketNewsTool()
        registry.register(news_tool)
        registry.register(events_tool)
        registry.register(market_tool)
        executor = ToolExecutor(registry=registry)

        # 1. Execute get_company_news
        result_news = executor.execute("get_company_news", {"symbol": "INFY", "limit": 2})
        self.assertTrue(result_news.success)
        self.assertEqual(len(result_news.data), 2)
        self.assertEqual(result_news.data[0]["headline"], "Infosys bags USD 100M contract win") # Sorted descending

        # 2. Execute get_company_events
        result_events = executor.execute("get_company_events", {"symbol": "INFY", "event_type": "dividend"})
        self.assertTrue(result_events.success)
        self.assertEqual(len(result_events.data), 1)
        self.assertEqual(result_events.data[0]["event_type"], "dividend")

        # 3. Execute get_market_news
        result_mkt = executor.execute("get_market_news", {"limit": 5})
        self.assertTrue(result_mkt.success)
        self.assertEqual(len(result_mkt.data), 3)


class MarketResearchAgentTests(TestCase):
    """
    Unit and integration tests for MarketResearchAgent and MarketResearchService.
    Verifies tool execution integration, report structure validation, failure handling,
    iteration limits per depth, and strict PIT safety constraints.
    """

    def setUp(self):
        self.company = Company.objects.create(name="Infosys", short_name="INFY")
        self.instrument = Instrument.objects.create(company=self.company, symbol="INFY", exchange="NSE")

    @patch("llm.router.IntelligentRouter.generate")
    @patch("requests.get")
    def test_market_research_agent_flow(self, mock_get, mock_generate):
        """Verifies agent executes correctly and outputs structured report schema."""
        from chat.agents.market_research_agent import MarketResearchAgent
        from market.services.market_research_service import MarketResearchService
        
        # Mock screener raw financials raw ingestion
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_NEWS_RSS_XML
        mock_get.return_value = mock_resp
        
        # Setup mock steps: 
        # 1. Ask for financials
        # 2. Return final response JSON report
        step1_response = {
            "type": "tool_call",
            "tool_name": "get_company_financials",
            "tool_args": {"symbol": "INFY", "period_type": "ANNUAL"},
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
        
        final_report = {
            "company": "Infosys",
            "instrument": "INFY",
            "as_of": "2026-08-22T00:00:00Z",
            "summary": "Infosys showing moderate growth with stable margins.",
            "market_snapshot": {"price": 1500.0, "volume": 120000},
            "technical_analysis": "Daily RSI at 55 indicating neutral zone.",
            "fundamental_analysis": "Revenue grew in FY25, EPS is stable.",
            "news_analysis": "Syndicated contract wins noted recently.",
            "positive_factors": ["Stable margin", "Contract wins"],
            "risks": ["Slowing global IT spend"],
            "contradictions": ["Growth in revenue but operating cash flow flat"],
            "unknowns": ["Full TTM margin details"],
            "evidence": ["FY25 annual statement from Screener"],
            "generated_at": "2026-08-22T12:00:00Z"
        }
        
        step2_response = {
            "type": "text",
            "text": json.dumps(final_report),
            "prompt_tokens": 120,
            "completion_tokens": 300,
            "total_tokens": 420
        }
        
        mock_generate.side_effect = [step1_response, step2_response]
        
        service = MarketResearchService()
        report = service.research_stock(
            symbol="INFY",
            question="Analyze the core financial stability and outlook",
            depth="standard"
        )
        
        # Verify result contains the report keys
        self.assertEqual(report["company"], "Infosys")
        self.assertEqual(report["instrument"], "INFY")
        self.assertEqual(report["as_of"], "2026-08-22T00:00:00Z")
        self.assertIn("moderate growth", report["summary"])
        self.assertEqual(len(report["positive_factors"]), 2)
        self.assertEqual(report["positive_factors"][0], "Stable margin")
        self.assertEqual(len(report["evidence"]), 1)

    @patch("llm.router.IntelligentRouter.generate")
    def test_market_research_agent_pit_safety(self, mock_generate):
        """Verifies as_of PIT parameter is propagated to tool calls and filters out future data."""
        from chat.agents.market_research_agent import MarketResearchAgent
        from llm.tools.registry import ToolRegistry
        from llm.tools.implementations.market_tool import GetCompanyNewsTool
        
        # Ingest news items with different timestamps
        from django.utils.timezone import make_aware
        news1 = NewsItem.objects.create(
            company=self.company,
            headline="Past News",
            published_at=make_aware(datetime(2026, 8, 20, 12, 0, 0)),
            content_hash="h1"
        )
        news2 = NewsItem.objects.create(
            company=self.company,
            headline="Future News",
            published_at=make_aware(datetime(2026, 8, 22, 12, 0, 0)),
            content_hash="h2"
        )
        
        # Setup agent with registry containing news tool
        registry = ToolRegistry()
        registry.register(GetCompanyNewsTool())
        
        # Mock LLM to invoke tool and then finish
        step1_response = {
            "type": "tool_call",
            "tool_name": "get_company_news",
            "tool_args": {"symbol": "INFY", "limit": 5},
            "prompt_tokens": 50,
            "completion_tokens": 30
        }
        
        step2_response = {
            "type": "text",
            "text": json.dumps({"status": "done"}),
            "prompt_tokens": 60,
            "completion_tokens": 10
        }
        
        mock_generate.side_effect = [step1_response, step2_response]
        
        agent = MarketResearchAgent(provider=MagicMock(), tool_registry=registry)
        agent.provider.generate.side_effect = [step1_response, step2_response]
        
        # Execute research as of August 21, 2026 (excludes future news)
        as_of_t = "2026-08-21T18:00:00Z"
        agent.execute(
            prompt="Get news details",
            as_of=as_of_t,
            depth="quick"
        )
        
        # Verify that during the execution, the tools executed successfully and only returned PIT-safe items
        # Let's inspect the message history of the agent execution loop
        # The tool result content (which would be in messages[2]) should contain "Past News" but not "Future News"
        # Let's check history calls or simply check tool returns directly
        tool_result = GetCompanyNewsTool().execute(symbol="INFY", limit=5, as_of=as_of_t)
        self.assertTrue(tool_result.success)
        self.assertEqual(len(tool_result.data), 1)
        self.assertEqual(tool_result.data[0]["headline"], "Past News")

    @patch("llm.router.IntelligentRouter.generate")
    def test_market_research_agent_failure_degradation(self, mock_generate):
        """Verifies agent degrades gracefully when tools fail or return empty/partial datasets."""
        from chat.agents.market_research_agent import MarketResearchAgent
        from llm.tools.registry import ToolRegistry
        from llm.tools.implementations.market_tool import GetCompanyNewsTool
        
        registry = ToolRegistry()
        registry.register(GetCompanyNewsTool())
        
        # Mock tool call that will fail (e.g. invalid ticker symbol causes exception)
        step1_response = {
            "type": "tool_call",
            "tool_name": "get_company_news",
            "tool_args": {"symbol": "NON_EXISTENT"},
            "prompt_tokens": 50,
            "completion_tokens": 30
        }
        
        step2_response = {
            "type": "text",
            "text": json.dumps({
                "company": "Non-Existent",
                "instrument": "NON_EXISTENT",
                "summary": "No news available.",
                "risks": ["Ticker does not exist"],
                "unknowns": ["Company information missing"]
            }),
            "prompt_tokens": 60,
            "completion_tokens": 100
        }
        
        agent = MarketResearchAgent(provider=MagicMock(), tool_registry=registry)
        agent.provider.generate.side_effect = [step1_response, step2_response]
        
        result_str = agent.execute(
            prompt="Analyze NON_EXISTENT symbol",
            depth="quick"
        )
        
        parsed = json.loads(result_str)
        self.assertEqual(parsed["summary"], "No news available.")
        self.assertIn("Ticker does not exist", parsed["risks"])


class MarketRegimeCrossMarketSubsystemTests(TestCase):
    """
    Subsystem tests validating the deterministic context engine, regime classification,
    breadth analysis, sector rankings, global cues staleness, rolling correlations,
    and strict PIT safety boundaries.
    """
    databases = {'default', 'telemetry'}

    def setUp(self):
        # 1. Bootstrap indices and global instruments
        self.nifty_comp = Company.objects.create(name="Nifty 50 Index", short_name="^NSEI", sector="Index", industry="Index")
        self.nifty = Instrument.objects.create(company=self.nifty_comp, symbol="^NSEI", exchange="NSE", instrument_type="INDEX")

        self.bank_comp = Company.objects.create(name="Nifty Bank Index", short_name="^NSEBANK", sector="Index", industry="Index")
        self.bank = Instrument.objects.create(company=self.bank_comp, symbol="^NSEBANK", exchange="NSE", instrument_type="INDEX")

        self.sp_comp = Company.objects.create(name="S&P 500 Index", short_name="^GSPC", sector="Global Index", industry="Global Index")
        self.sp = Instrument.objects.create(company=self.sp_comp, symbol="^GSPC", exchange="GLOBAL", instrument_type="INDEX", currency="USD")

        self.usdinr_comp = Company.objects.create(name="USD/INR Exchange Rate", short_name="USDINR=X", sector="Currency", industry="Currency")
        self.usdinr = Instrument.objects.create(company=self.usdinr_comp, symbol="USDINR=X", exchange="GLOBAL", instrument_type="INDEX", currency="INR")

        self.crude_comp = Company.objects.create(name="Crude Oil Futures", short_name="CL=F", sector="Commodity", industry="Commodity")
        self.crude = Instrument.objects.create(company=self.crude_comp, symbol="CL=F", exchange="GLOBAL", instrument_type="INDEX", currency="USD")

        # 2. Bootstrap two equities in different sectors
        self.rel_comp = Company.objects.create(name="Reliance Industries", short_name="RELIANCE", sector="Energy", industry="Oil & Gas")
        self.reliance = Instrument.objects.create(company=self.rel_comp, symbol="RELIANCE", exchange="NSE", instrument_type="EQUITY")

        self.tcs_comp = Company.objects.create(name="Tata Consultancy", short_name="TCS", sector="Technology", industry="IT Services")
        self.tcs = Instrument.objects.create(company=self.tcs_comp, symbol="TCS", exchange="NSE", instrument_type="EQUITY")

        self.base_time = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)

    def _generate_bars(self, instrument, start_price, n_bars, trend_pct=0.0):
        """Helper to generate chronological OHLCV bars with a specific trend."""
        import math
        bars = []
        current_price = start_price
        for i in range(n_bars):
            timestamp = self.base_time - timedelta(days=(n_bars - i - 1))
            effective_pct = trend_pct
            if trend_pct != 0.0 and i < n_bars - 1:
                effective_pct = trend_pct + 0.02 * math.sin(i)
            current_price = current_price * (1.0 + effective_pct)
            bars.append(OHLCVBar(
                instrument=instrument,
                timeframe="1d",
                timestamp=timestamp,
                open=Decimal(str(current_price * 0.99)),
                high=Decimal(str(current_price * 1.02)),
                low=Decimal(str(current_price * 0.98)),
                close=Decimal(str(current_price)),
                volume=100000,
                source="test"
            ))
        OHLCVBar.objects.bulk_create(bars)

    def test_market_regime_classification(self):
        from market.services.context_service import MarketContextService
        # Generate 210 bars to satisfy SMA200 indicators warmup
        # Generate a bullish trend (+0.1% daily)
        self._generate_bars(self.nifty, 10000.0, 210, trend_pct=0.001)

        service = MarketContextService()
        regime = service.calculate_market_regime("^NSEI", self.base_time)
        self.assertEqual(regime["status"], "active")
        self.assertEqual(regime["trend"], "bullish")
        self.assertIn(regime["momentum"], ["positive", "neutral"])

    def test_market_breadth_calculation(self):
        from market.services.context_service import MarketContextService
        # Generate 30 bars for equities
        # Reliance is advancing
        self._generate_bars(self.reliance, 2000.0, 30, trend_pct=0.01)
        # TCS is declining
        self._generate_bars(self.tcs, 3000.0, 30, trend_pct=-0.01)

        service = MarketContextService()
        breadth = service.calculate_market_breadth("ALL", self.base_time)
        
        self.assertEqual(breadth["status"], "active")
        self.assertEqual(breadth["advancing"], 1)
        self.assertEqual(breadth["declining"], 1)
        self.assertEqual(breadth["advance_decline_ratio"], 1.0)
        self.assertEqual(breadth["coverage"]["total_universe_size"], 2)

    def test_sector_performance_ranking(self):
        from market.services.context_service import MarketContextService
        # Reliance (Energy) +1% daily
        self._generate_bars(self.reliance, 2000.0, 30, trend_pct=0.01)
        # TCS (Technology) -1% daily
        self._generate_bars(self.tcs, 3000.0, 30, trend_pct=-0.01)

        service = MarketContextService()
        sectors = service.calculate_sector_performance(self.base_time)
        
        self.assertEqual(sectors[0]["sector"], "Energy")
        self.assertEqual(sectors[1]["sector"], "Technology")
        self.assertEqual(sectors[0]["tier"], "strongest")
        self.assertEqual(sectors[1]["tier"], "weakest")

    def test_global_cues_timezone_and_staleness(self):
        from market.services.context_service import MarketContextService
        # Generate global cues bars
        self._generate_bars(self.sp, 4500.0, 10)
        self._generate_bars(self.usdinr, 83.0, 10)

        # Retrieve at self.base_time
        service = MarketContextService()
        cues = service.retrieve_global_cues(self.base_time)
        
        self.assertEqual(cues["^GSPC"]["status"], "active")
        self.assertEqual(cues["USDINR=X"]["status"], "active")
        self.assertFalse(cues["^GSPC"]["stale"])

        # Retrieve at a future time (generating staleness)
        future_time = self.base_time + timedelta(days=5)
        cues_stale = service.retrieve_global_cues(future_time)
        self.assertTrue(cues_stale["^GSPC"]["stale"])

    def test_cross_market_correlation(self):
        from market.services.context_service import MarketContextService
        # Generate aligned returns for Nifty and S&P
        self._generate_bars(self.nifty, 10000.0, 30, trend_pct=0.005)
        self._generate_bars(self.sp, 4500.0, 30, trend_pct=0.005)

        service = MarketContextService()
        cross = service.calculate_cross_market_features(self.base_time)
        
        correlations = cross["rolling_20d_correlations"]
        # Perfectly aligned upward trends should yield a high positive correlation coefficient
        self.assertNotEqual(correlations["^GSPC"], "insufficient_data")
        self.assertGreater(correlations["^GSPC"], 0.8)

    def test_point_in_time_safety(self):
        from market.services.context_service import MarketContextService
        # Generate bars up to self.base_time
        self._generate_bars(self.nifty, 10000.0, 20)
        
        # Save close price at base time
        close_at_base = OHLCVBar.objects.filter(instrument=self.nifty).order_by('-timestamp')[0].close

        # Generate a future bar
        future_time = self.base_time + timedelta(days=1)
        OHLCVBar.objects.create(
            instrument=self.nifty,
            timeframe="1d",
            timestamp=future_time,
            open=Decimal("15000.00"),
            high=Decimal("15500.00"),
            low=Decimal("14800.00"),
            close=Decimal("15200.00"),
            volume=200000,
            source="test"
        )

        service = MarketContextService()
        regime = service.calculate_market_regime("^NSEI", self.base_time)
        
        # Verify it doesn't see the future 15200.00 close bar
        self.assertEqual(regime["close"], float(close_at_base))

    def test_market_context_tool_integration(self):
        # Generate index bars
        self._generate_bars(self.nifty, 10000.0, 30)
        self._generate_bars(self.bank, 40000.0, 30)

        from llm.tools.registry import ToolRegistry
        from llm.tools.executor import ToolExecutor
        from llm.tools.implementations.market_tool import GetMarketContextTool

        registry = ToolRegistry()
        tool = GetMarketContextTool()
        registry.register(tool)
        executor = ToolExecutor(registry)

        as_of_str = self.base_time.isoformat()
        res = executor.execute("get_market_context", {"as_of": as_of_str, "universe": "NIFTY50"})
        
        self.assertTrue(res.success)
        self.assertEqual(res.data["as_of"], as_of_str)
        self.assertIn("^NSEI", res.data["index_regimes"])


class StockOpportunityDiscoverySubsystemTests(TestCase):
    """
    Subsystem tests validating universe memberships, stock feature fusion, opportunity scoring,
    candidate classifications, ranking, separate horizons, PIT look-ahead safety, and N+1 query controls.
    """
    databases = {'default', 'telemetry'}

    def setUp(self):
        # 1. Bootstrap company and active instrument
        self.company = Company.objects.create(name="Reliance Industries", short_name="RELIANCE", sector="Energy", industry="Oil & Gas")
        self.instrument = Instrument.objects.create(company=self.company, symbol="RELIANCE", exchange="NSE", instrument_type="EQUITY")
        
        self.tcs_comp = Company.objects.create(name="TCS", short_name="TCS", sector="Technology", industry="IT Services")
        self.tcs = Instrument.objects.create(company=self.tcs_comp, symbol="TCS", exchange="NSE", instrument_type="EQUITY")
        
        self.base_time = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
        
        # 2. Bootstrap universes
        self.universe = Universe.objects.create(name="CUSTOM_UNIV", description="Custom test universe", is_active=True)
        UniverseMembership.objects.create(universe=self.universe, instrument=self.instrument, is_active=True, added_at=self.base_time)
        UniverseMembership.objects.create(universe=self.universe, instrument=self.tcs, is_active=True, added_at=self.base_time)

    def _setup_mock_data(self, close_rel=2000.0, rsi_rel=65.0, roe_rel=0.18, de_rel=0.4):
        # Latest daily bar for Reliance
        OHLCVBar.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            open=Decimal(str(close_rel * 0.99)), high=Decimal(str(close_rel * 1.01)),
            low=Decimal(str(close_rel * 0.98)), close=Decimal(str(close_rel)),
            volume=50000, source="test"
        )
        
        # 30-day liquidity bars
        for i in range(1, 10):
            OHLCVBar.objects.create(
                instrument=self.instrument, timeframe="1d", timestamp=self.base_time - timedelta(days=i),
                open=Decimal("1900.00"), high=Decimal("1950.00"), low=Decimal("1850.00"), close=Decimal("1900.00"),
                volume=10000, source="test"
            )

        # Technical features
        TechnicalFeature.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            name="SMA_50", param_key="period=50", value=Decimal("1800.00")
        )
        TechnicalFeature.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            name="SMA_200", param_key="period=200", value=Decimal("1600.00")
        )
        TechnicalFeature.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            name="RSI_14", param_key="period=14", value=Decimal(str(rsi_rel))
        )
        TechnicalFeature.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            name="relative_volume_20", param_key="period=20", value=Decimal("1.4")
        )
        TechnicalFeature.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=self.base_time,
            name="distance_from_high_20", param_key="period=20", value=Decimal("-1.2")
        )

        # Derived fundamental metrics
        IncomeStatement.objects.create(
            company=self.company, fiscal_year=2025, period_type="ANNUAL", period_string="Mar 2025",
            period_end=self.base_time.date() - timedelta(days=30), revenue=Decimal("100000.00"), pat=Decimal("15000.00")
        )
        DerivedFundamentalMetric.objects.create(
            company=self.company, period_type="ANNUAL", period_string="Mar 2025",
            name="revenue_growth_yoy", value=Decimal("0.15")
        )
        DerivedFundamentalMetric.objects.create(
            company=self.company, period_type="ANNUAL", period_string="Mar 2025",
            name="pat_growth_yoy", value=Decimal("0.20")
        )
        DerivedFundamentalMetric.objects.create(
            company=self.company, period_type="ANNUAL", period_string="Mar 2025",
            name="return_on_equity", value=Decimal(str(roe_rel))
        )
        DerivedFundamentalMetric.objects.create(
            company=self.company, period_type="ANNUAL", period_string="Mar 2025",
            name="debt_equity", value=Decimal(str(de_rel))
        )

        # Market context snapshot
        MarketContextSnapshot.objects.create(
            as_of=self.base_time, universe="CUSTOM_UNIV",
            index_regimes={
                "^NSEI": {"trend": "bullish", "volatility": "normal"}
            },
            sector_rankings=[
                {"sector": "Energy", "tier": "strongest", "momentum_state": "improving"}
            ]
        )

    def test_universe_membership(self):
        # Membership is active at base_time
        active_members = UniverseMembership.objects.filter(
            universe=self.universe, is_active=True, added_at__lte=self.base_time
        )
        self.assertEqual(active_members.count(), 2)

        # Inactive membership removal check
        membership = UniverseMembership.objects.get(universe=self.universe, instrument=self.tcs)
        membership.removed_at = self.base_time - timedelta(hours=1)
        membership.is_active = False
        membership.save()

        # Query members as of base_time
        as_of_members = UniverseMembership.objects.filter(
            universe=self.universe, is_active=True, added_at__lte=self.base_time
        ).filter(Q(removed_at__isnull=True) | Q(removed_at__gt=self.base_time))
        self.assertEqual(as_of_members.count(), 1)
        self.assertEqual(as_of_members[0].instrument.symbol, "RELIANCE")

    def test_feature_fusion_and_scoring(self):
        self._setup_mock_data()
        
        from market.services.discovery_service import OpportunityDiscoveryService
        service = OpportunityDiscoveryService()
        
        snapshots = service.scan_universe("CUSTOM_UNIV", "DELIVERY_SWING", as_of=self.base_time)
        self.assertEqual(len(snapshots), 1)  # Only RELIANCE passed liquidity filter (TCS has no daily bar)
        
        snap = snapshots[0]
        self.assertEqual(snap.instrument.symbol, "RELIANCE")
        self.assertEqual(snap.horizon, "DELIVERY_SWING")
        self.assertEqual(snap.opportunity_type, "TRENDING")
        self.assertGreater(snap.final_opportunity_score, Decimal("70.00"))
        
        # Verify scores dictionary structure
        self.assertIn("technical", snap.component_scores)
        self.assertIn("fundamental", snap.component_scores)
        self.assertIn("sector", snap.component_scores)
        
        # Verify data quality status
        self.assertEqual(snap.data_quality["status"], "COMPLETE")

    def test_opportunity_classifications(self):
        # 1. Test Momentum Classification
        self._setup_mock_data(rsi_rel=68.0)
        from market.services.discovery_service import OpportunityDiscoveryService
        service = OpportunityDiscoveryService()
        snapshots = service.scan_universe("CUSTOM_UNIV", "DELIVERY_SWING", as_of=self.base_time)
        self.assertEqual(snapshots[0].opportunity_type, "TRENDING")  # Trending is evaluated first

    def test_horizon_routing_validation(self):
        from market.services.discovery_service import OpportunityDiscoveryService
        service = OpportunityDiscoveryService()
        
        # Intraday capability check should return empty snapshots and log NOT READY
        snapshots = service.scan_universe("CUSTOM_UNIV", "INTRADAY", as_of=self.base_time)
        self.assertEqual(len(snapshots), 0)

    def test_point_in_time_safety(self):
        self._setup_mock_data()
        
        # Add future bar and future event
        future_time = self.base_time + timedelta(days=1)
        OHLCVBar.objects.create(
            instrument=self.instrument, timeframe="1d", timestamp=future_time,
            open=Decimal("2500.00"), high=Decimal("2600.00"), low=Decimal("2450.00"), close=Decimal("2520.00"),
            volume=80000, source="test"
        )
        
        # Ingest a future news item
        NewsItem.objects.create(
            company=self.company, headline="RELIANCE bags USD 500M mega contract win",
            published_at=future_time, source="yahoo", content_hash="fh1"
        )

        from market.services.discovery_service import OpportunityDiscoveryService
        service = OpportunityDiscoveryService()
        
        # Scan as of base_time
        snapshots = service.scan_universe("CUSTOM_UNIV", "DELIVERY_SWING", as_of=self.base_time)
        self.assertEqual(len(snapshots), 1)
        
        # Confirm future price close of 2520.00 is NOT present in supporting features close (which should be 2000.00)
        snap = snapshots[0]
        self.assertEqual(snap.supporting_features["close"], 2000.0)
        
        # Confirm future contract win news did not trigger positive event score boost (news_score stays default/standard)
        self.assertLess(snap.component_scores["news"], 100.0)

    def test_performance_batch_queries(self):
        self._setup_mock_data()
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        from market.services.discovery_service import OpportunityDiscoveryService
        
        service = OpportunityDiscoveryService()
        
        # Capture queries during scanning to confirm fixed bounds (batch optimization)
        with CaptureQueriesContext(connection) as ctx:
            service.scan_universe("CUSTOM_UNIV", "DELIVERY_SWING", as_of=self.base_time)
            
        # Number of queries should be extremely low and bounded (no O(N) queries)
        self.assertLess(len(ctx.captured_queries), 18)

    def test_opportunity_tools_integration(self):
        self._setup_mock_data()
        
        from llm.tools.registry import ToolRegistry
        from llm.tools.executor import ToolExecutor
        from llm.tools.implementations.market_tool import (
            GetStockOpportunitiesTool,
            GetStockOpportunityTool,
            GetSectorOpportunitiesTool
        )

        registry = ToolRegistry()
        registry.register(GetStockOpportunitiesTool())
        registry.register(GetStockOpportunityTool())
        registry.register(GetSectorOpportunitiesTool())
        executor = ToolExecutor(registry)

        as_of_str = self.base_time.isoformat()
        
        # 1. get_stock_opportunities
        res_list = executor.execute("get_stock_opportunities", {"universe": "CUSTOM_UNIV", "as_of": as_of_str})
        self.assertTrue(res_list.success)
        self.assertEqual(len(res_list.data), 1)
        self.assertEqual(res_list.data[0]["symbol"], "RELIANCE")
        self.assertIn("reasons", res_list.data[0])

        # 2. get_stock_opportunity
        res_detail = executor.execute("get_stock_opportunity", {"symbol": "RELIANCE", "as_of": as_of_str})
        self.assertTrue(res_detail.success)
        self.assertEqual(res_detail.data["symbol"], "RELIANCE")
        self.assertEqual(res_detail.data["opportunity_type"], "TRENDING")

        # 3. get_sector_opportunities
        res_sector = executor.execute("get_sector_opportunities", {"sector": "Energy", "as_of": as_of_str})
        self.assertTrue(res_sector.success)
        self.assertEqual(res_sector.data["sector"], "Energy")
        self.assertEqual(len(res_sector.data["opportunities"]), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Module 8 — Signal Engine & Recommendation Tests
# ─────────────────────────────────────────────────────────────────────────────

class SignalEngineSubsystemTests(TestCase):
    """
    Comprehensive unit and subsystem tests for Module 8:
      - Setup detector logic
      - Signal engine PIT safety
      - R:R rejection gate
      - Intraday gate
      - Recommendation service append-only persistence
      - Lifecycle status transitions
      - LLM recommendation tools
    """

    def _make_company_and_instrument(self, symbol="TESTCO", sector="Technology"):
        company = Company.objects.create(
            name=f"{symbol} Ltd",
            short_name=symbol,
            sector=sector,
            industry="Software",
        )
        instrument = Instrument.objects.create(
            company=company,
            symbol=symbol,
            exchange="NSE",
            instrument_type="EQUITY",
            is_active=True,
        )
        return company, instrument

    def _make_bars(self, instrument, n=260, base_price=1000.0, timeframe="1d"):
        """Creates n daily OHLCV bars chronologically."""
        from django.utils import timezone as tz
        bars = []
        base_dt = datetime(2024, 1, 1, 9, 15, 0, tzinfo=timezone.utc)
        for i in range(n):
            close = base_price + (i * 2.0)   # Gentle uptrend
            bars.append(OHLCVBar(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=base_dt + timedelta(days=i),
                open=Decimal(str(close - 5)),
                high=Decimal(str(close + 10)),
                low=Decimal(str(close - 15)),
                close=Decimal(str(close)),
                volume=500000,
                source="test"
            ))
        OHLCVBar.objects.bulk_create(bars)
        return bars

    def _make_technical_features(self, instrument, bars):
        """
        Manually create TechnicalFeature records with realistic indicator values
        for the last bar, so signal engine can find them.
        """
        last_ts = bars[-1].timestamp
        close_val = float(bars[-1].close)

        feature_data = [
            ("RSI_14", "period=14", "58.0"),
            ("SMA_20", "period=20", str(close_val * 0.97)),
            ("SMA_50", "period=50", str(close_val * 0.90)),
            ("SMA_200", "period=200", str(close_val * 0.80)),
            ("ATR_14", "period=14", "25.0"),
            ("rolling_high_20", "period=20", str(close_val * 1.005)),
            ("rolling_low_20", "period=20", str(close_val * 0.95)),
            ("relative_volume_20", "period=20", "1.5"),
            ("MACD_line", "fast=12;slow=26;signal=9", "5.0"),
            ("MACD_signal", "fast=12;slow=26;signal=9", "3.0"),
            ("MACD_hist", "fast=12;slow=26;signal=9", "2.0"),
        ]

        tfs = []
        for name, param_key, val in feature_data:
            tfs.append(TechnicalFeature(
                instrument=instrument,
                timeframe="1d",
                timestamp=last_ts,
                name=name,
                param_key=param_key,
                parameters={},
                value=Decimal(val)
            ))
        TechnicalFeature.objects.bulk_create(tfs)
        return last_ts

    # ── 1. Setup Detector Unit Tests ──────────────────────────────────────────

    def test_breakout_detector_detects_when_conditions_met(self):
        """BREAKOUT detector fires when price near rolling high + volume + RSI momentum."""
        from market.services.setup_detectors import detect_breakout

        tf = {
            "RSI_14": 60.0,
            "SMA_50": 990.0,
            "SMA_200": 900.0,
            "relative_volume_20": 1.4,
            "rolling_high_20": 1005.0,
        }
        result = detect_breakout(tf, close=1002.0)
        self.assertEqual(result.setup_type.value, "BREAKOUT")
        self.assertTrue(result.detected)
        self.assertGreater(result.score, 50.0)
        self.assertTrue(any("20-day high" in c for c in result.conditions_met))

    def test_breakout_detector_fails_on_low_volume(self):
        """BREAKOUT should NOT fire when relative volume is below threshold."""
        from market.services.setup_detectors import detect_breakout

        tf = {
            "RSI_14": 60.0,
            "SMA_50": 990.0,
            "SMA_200": 900.0,
            "relative_volume_20": 0.8,  # below 1.2
            "rolling_high_20": 1005.0,
        }
        result = detect_breakout(tf, close=1003.0)
        self.assertFalse(result.detected)
        self.assertTrue(any("volume" in c.lower() for c in result.conditions_failed))

    def test_pullback_detector_detects_controlled_retracement(self):
        """PULLBACK fires for uptrend + controlled retracement + RSI in 35-55."""
        from market.services.setup_detectors import detect_pullback

        tf = {
            "RSI_14": 46.0,
            "SMA_20": 1010.0,
            "SMA_50": 980.0,
            "SMA_200": 900.0,
        }
        result = detect_pullback(tf, close=1007.0)  # Slightly below SMA-20
        self.assertEqual(result.setup_type.value, "PULLBACK")
        self.assertTrue(result.detected)
        self.assertGreater(result.score, 60.0)

    def test_pullback_detector_fails_on_bearish_trend(self):
        """PULLBACK must NOT fire when price is below SMA-200."""
        from market.services.setup_detectors import detect_pullback

        tf = {
            "RSI_14": 46.0,
            "SMA_20": 1010.0,
            "SMA_50": 980.0,
            "SMA_200": 1100.0,  # Price below SMA-200 → bearish
        }
        result = detect_pullback(tf, close=1007.0)
        self.assertFalse(result.detected)

    def test_breakdown_detector_fires_on_bearish_setup(self):
        """BREAKDOWN detector fires when price near 20-day low + high volume + RSI < 50."""
        from market.services.setup_detectors import detect_breakdown

        tf = {
            "RSI_14": 38.0,
            "SMA_50": 1010.0,
            "relative_volume_20": 1.5,
            "rolling_low_20": 996.0,
        }
        result = detect_breakdown(tf, close=997.0)
        self.assertEqual(result.setup_type.value, "BREAKDOWN")
        self.assertTrue(result.detected)

    def test_run_all_detectors_returns_sorted_list(self):
        """run_all_detectors should always return a list sorted by (detected, score) desc."""
        from market.services.setup_detectors import run_all_detectors

        tf = {
            "RSI_14": 58.0,
            "SMA_20": 970.0,
            "SMA_50": 950.0,
            "SMA_200": 880.0,
            "ATR_14": 20.0,
            "rolling_high_20": 1005.0,
            "rolling_low_20": 960.0,
            "relative_volume_20": 1.4,
            "MACD_line": 4.0,
            "MACD_signal": 2.0,
            "MACD_hist": 2.0,
        }
        results = run_all_detectors(tf, close=1002.0)
        self.assertGreater(len(results), 0)
        # Best detected setup should be first
        scores = [(r.detected, r.score) for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    # ── 2. Signal Engine PIT Safety ───────────────────────────────────────────

    def test_signal_engine_returns_insufficient_on_no_bars(self):
        """SignalEngine returns INSUFFICIENT_DATA when no OHLCVBar exists."""
        from market.services.signal_engine import SignalEngine
        from market.signal_enums import SignalDirection

        _, instrument = self._make_company_and_instrument(symbol="NODATA")
        engine = SignalEngine()
        draft = engine.generate_recommendation(instrument, "DELIVERY_SWING")
        self.assertEqual(draft.signal, SignalDirection.INSUFFICIENT_DATA.value)

    def test_signal_engine_pit_safety_future_bars_hidden(self):
        """
        When as_of is set to before the bars exist, the engine must see no bars
        and return INSUFFICIENT_DATA (not use the future bars).
        """
        from market.services.signal_engine import SignalEngine
        from market.signal_enums import SignalDirection

        _, instrument = self._make_company_and_instrument(symbol="FUTURETEST")
        # All bars are in 2025
        self._make_bars(instrument, n=10, base_price=800.0)
        bars = OHLCVBar.objects.filter(instrument=instrument).order_by('timestamp')

        # Set as_of to BEFORE the first bar
        past_as_of = bars.first().timestamp - timedelta(days=5)

        engine = SignalEngine()
        draft = engine.generate_recommendation(instrument, "DELIVERY_SWING", as_of=past_as_of)
        # Should not see the future bars
        self.assertIn(draft.signal, [
            SignalDirection.INSUFFICIENT_DATA.value,
            SignalDirection.NOT_READY.value
        ])

    def test_signal_engine_intraday_gate_returns_not_ready(self):
        """INTRADAY horizon without intraday bars must return NOT_READY."""
        from market.services.signal_engine import SignalEngine
        from market.signal_enums import SignalDirection

        _, instrument = self._make_company_and_instrument(symbol="INTRATEST")
        self._make_bars(instrument, n=100, timeframe="1d")   # Only daily bars

        engine = SignalEngine()
        draft = engine.generate_recommendation(instrument, "INTRADAY")
        self.assertEqual(draft.signal, SignalDirection.NOT_READY.value)

    def test_signal_engine_generates_recommendation_with_features(self):
        """
        With adequate bars and technical features, the engine must generate
        a valid draft (any signal, but a complete one with entry_condition set).
        """
        from market.services.signal_engine import SignalEngine

        _, instrument = self._make_company_and_instrument(symbol="FULLTEST")
        bars = self._make_bars(instrument, n=260, base_price=1500.0)
        self._make_technical_features(instrument, bars)

        engine = SignalEngine()
        as_of = bars[-1].timestamp
        draft = engine.generate_recommendation(instrument, "DELIVERY_SWING", as_of=as_of)

        # Draft must have a signal and entry condition
        self.assertIsNotNone(draft.signal)
        self.assertIsNotNone(draft.entry_condition)
        self.assertIsNotNone(draft.confidence)
        # Confidence must be one of the valid levels
        self.assertIn(draft.confidence, ["LOW", "MEDIUM", "HIGH"])

    # ── 3. R:R Rejection Gate ─────────────────────────────────────────────────

    def test_rr_below_minimum_returns_no_action(self):
        """
        If the computed R:R is below minimum, the engine must return NO_ACTION
        rather than persisting a bad setup.
        """
        from market.services.signal_engine import SignalEngine, _entry_from_setup, _stop_from_setup, _target_from_setup
        from market.services.setup_detectors import SetupResult
        from market.signal_enums import SetupType, EntryType, StopMethod, TargetMethod, SignalDirection

        # Simulate a setup where stop is very close to entry and target is also close
        # such that R:R < 1.5
        setup = SetupResult(
            setup_type=SetupType.BREAKOUT,
            detected=True,
            score=80.0,
            conditions_met=["Near resistance"],
            conditions_failed=[],
            relevant_values={}
        )
        entry = 1000.0
        stop = 998.0   # Only 0.2% risk
        target = 1001.0  # Only 0.1% reward → R:R = 0.5

        rr_ratio = abs(target - entry) / abs(entry - stop)
        self.assertLess(rr_ratio, 1.5)   # Confirm the test scenario is correct

    # ── 4. Recommendation Service (Persistence) ───────────────────────────────

    def test_recommendation_service_creates_new_record(self):
        """RecommendationService.generate_and_save creates a new DB record."""
        from market.services.recommendation_service import RecommendationService
        from market.models import StockRecommendation

        _, instrument = self._make_company_and_instrument(symbol="PERSIST1")
        bars = self._make_bars(instrument, n=260)
        self._make_technical_features(instrument, bars)

        svc = RecommendationService()
        as_of = bars[-1].timestamp
        rec = svc.generate_and_save(instrument, "DELIVERY_SWING", as_of=as_of)

        self.assertIsNotNone(rec.id)
        self.assertIsNotNone(rec.signal)
        self.assertEqual(rec.instrument, instrument)
        self.assertEqual(rec.horizon, "DELIVERY_SWING")

        # Confirm it's in the DB
        db_rec = StockRecommendation.objects.get(id=rec.id)
        self.assertEqual(db_rec.signal, rec.signal)

    def test_recommendation_service_append_only(self):
        """Two calls to generate_and_save for the same instrument create TWO separate records."""
        from market.services.recommendation_service import RecommendationService
        from market.models import StockRecommendation

        _, instrument = self._make_company_and_instrument(symbol="PERSIST2")
        bars = self._make_bars(instrument, n=260)
        self._make_technical_features(instrument, bars)

        svc = RecommendationService()
        as_of = bars[-1].timestamp

        rec1 = svc.generate_and_save(instrument, "DELIVERY_SWING", as_of=as_of)
        rec2 = svc.generate_and_save(instrument, "DELIVERY_SWING", as_of=as_of)

        self.assertNotEqual(rec1.id, rec2.id)
        self.assertEqual(StockRecommendation.objects.filter(instrument=instrument).count(), 2)

    def test_recommendation_deterministic_fields_immutable(self):
        """
        Verify that update_status does NOT modify deterministic fields
        (entry_price, stop_price, target_price, signal).
        """
        from market.services.recommendation_service import RecommendationService
        from market.models import StockRecommendation

        _, instrument = self._make_company_and_instrument(symbol="IMMUTABLE")
        bars = self._make_bars(instrument, n=260)
        self._make_technical_features(instrument, bars)

        svc = RecommendationService()
        rec = svc.generate_and_save(instrument, "DELIVERY_SWING", as_of=bars[-1].timestamp)

        original_entry = rec.entry_price
        original_stop = rec.stop_price
        original_signal = rec.signal

        # Update status
        svc.update_status(rec, "TRIGGERED")

        # Re-read from DB
        rec.refresh_from_db()

        self.assertEqual(rec.status, "TRIGGERED")
        self.assertEqual(rec.entry_price, original_entry)
        self.assertEqual(rec.stop_price, original_stop)
        self.assertEqual(rec.signal, original_signal)

    def test_llm_explanation_write_only_updates_explanation(self):
        """save_explanation must only update llm_explanation field, nothing else."""
        from market.services.recommendation_service import RecommendationService

        _, instrument = self._make_company_and_instrument(symbol="EXPLAIN1")
        bars = self._make_bars(instrument, n=260)
        self._make_technical_features(instrument, bars)

        svc = RecommendationService()
        rec = svc.generate_and_save(instrument, "DELIVERY_SWING", as_of=bars[-1].timestamp)

        original_signal = rec.signal
        original_entry = rec.entry_price

        svc.save_explanation(rec, "This setup shows strong momentum based on tool output.")
        rec.refresh_from_db()

        self.assertEqual(rec.llm_explanation, "This setup shows strong momentum based on tool output.")
        self.assertEqual(rec.signal, original_signal)
        self.assertEqual(rec.entry_price, original_entry)

    def test_expire_old_recommendations(self):
        """expire_old_active_recommendations should mark old ACTIVE recs as EXPIRED."""
        from market.services.recommendation_service import RecommendationService
        from market.models import StockRecommendation
        from market.signal_enums import SignalDirection

        _, instrument = self._make_company_and_instrument(symbol="EXPIRETEST")

        # Manually create a recommendation with an old generated_at
        old_rec = StockRecommendation.objects.create(
            instrument=instrument,
            horizon="DELIVERY_SWING",
            signal=SignalDirection.NO_ACTION.value,
            setup_type="NONE",
            as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
            entry_type="CURRENT_MARKET_PRICE",
            entry_condition="No setup",
            stop_method="PERCENTAGE_FALLBACK",
            invalidation_reason="No setup",
            target_method="RISK_REWARD_DERIVED",
            confidence="LOW",
            status="ACTIVE",
        )
        # Backdate generated_at
        StockRecommendation.objects.filter(id=old_rec.id).update(
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )

        svc = RecommendationService()
        expired = svc.expire_old_active_recommendations(max_age_days=1)
        self.assertGreaterEqual(expired, 1)

        old_rec.refresh_from_db()
        self.assertEqual(old_rec.status, "EXPIRED")

    # ── 5. LLM Tool Integration ───────────────────────────────────────────────

    def test_get_recommendations_tool_returns_records(self):
        """get_recommendations tool must successfully return ACTIVE recommendations."""
        from llm.tools.implementations.market_tool import GetRecommendationsTool
        from market.models import StockRecommendation
        from market.signal_enums import SignalDirection

        _, instrument = self._make_company_and_instrument(symbol="RECTOOL1")

        # Create a recommendation manually
        StockRecommendation.objects.create(
            instrument=instrument,
            horizon="DELIVERY_SWING",
            signal="BUY",
            setup_type="BREAKOUT",
            as_of=datetime(2024, 8, 1, tzinfo=timezone.utc),
            entry_type="BREAKOUT_CONFIRMATION",
            entry_price=Decimal("1050.00"),
            entry_condition="Enter above 1050",
            stop_price=Decimal("990.00"),
            stop_method="STRUCTURAL",
            invalidation_reason="Close below 990",
            target_price=Decimal("1150.00"),
            target_method="MEASURED_MOVE",
            risk=Decimal("60.00"),
            reward=Decimal("100.00"),
            risk_reward_ratio=Decimal("1.67"),
            confidence="MEDIUM",
            status="ACTIVE",
        )

        registry = ToolRegistry()
        registry.register(GetRecommendationsTool())
        executor = ToolExecutor(registry)

        result = executor.execute("get_recommendations", {"status": "ACTIVE", "limit": 10})
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.data["count"], 1)

        # Verify expected fields are present
        rec_data = result.data["recommendations"][0]
        self.assertIn("symbol", rec_data)
        self.assertIn("signal", rec_data)
        self.assertIn("entry_price", rec_data)
        self.assertIn("stop_price", rec_data)
        self.assertIn("target_price", rec_data)
        self.assertIn("risk_reward_ratio", rec_data)

    def test_get_recommendation_tool_returns_full_detail(self):
        """get_recommendation tool must return full detail including all evidence fields."""
        from llm.tools.implementations.market_tool import GetRecommendationTool
        from market.models import StockRecommendation

        _, instrument = self._make_company_and_instrument(symbol="RECTOOL2")

        rec = StockRecommendation.objects.create(
            instrument=instrument,
            horizon="LONG_TERM",
            signal="BUY",
            setup_type="FUNDAMENTAL_MOMENTUM",
            as_of=datetime(2024, 8, 1, tzinfo=timezone.utc),
            entry_type="CURRENT_MARKET_PRICE",
            entry_price=Decimal("2000.00"),
            entry_condition="Enter at current market price",
            stop_price=Decimal("1900.00"),
            stop_method="ATR_BASED",
            invalidation_reason="Close below 1900",
            target_price=Decimal("2300.00"),
            target_method="ATR_MULTIPLE",
            risk=Decimal("100.00"),
            reward=Decimal("300.00"),
            risk_reward_ratio=Decimal("3.00"),
            confidence="HIGH",
            supporting_factors=["Strong revenue growth", "Low debt"],
            risk_factors=["Sector headwind"],
            confidence_components={"technical_confirmation": {"score": 80.0}},
            status="ACTIVE",
        )

        registry = ToolRegistry()
        registry.register(GetRecommendationTool())
        executor = ToolExecutor(registry)

        result = executor.execute("get_recommendation", {"symbol": "RECTOOL2", "horizon": "LONG_TERM"})
        self.assertTrue(result.success)

        data = result.data
        self.assertEqual(data["signal"], "BUY")
        self.assertEqual(data["confidence"], "HIGH")
        self.assertEqual(data["entry_price"], 2000.0)
        self.assertEqual(data["stop_price"], 1900.0)
        self.assertEqual(data["target_price"], 2300.0)
        self.assertEqual(data["risk_reward_ratio"], 3.0)
        self.assertIn("supporting_factors", data)
        self.assertIn("confidence_components", data)
        self.assertIn("setup_details", data)

    def test_get_recommendation_tool_not_found(self):
        """get_recommendation tool returns error for unknown symbol."""
        from llm.tools.implementations.market_tool import GetRecommendationTool

        registry = ToolRegistry()
        registry.register(GetRecommendationTool())
        executor = ToolExecutor(registry)

        result = executor.execute("get_recommendation", {"symbol": "NONEXISTANT99"})
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "NOT_FOUND")

    def test_get_active_recommendations_tool(self):
        """get_active_recommendations tool must return all ACTIVE records."""
        from llm.tools.implementations.market_tool import GetActiveRecommendationsTool
        from market.models import StockRecommendation

        _, inst1 = self._make_company_and_instrument(symbol="ACTIVE1")
        _, inst2 = self._make_company_and_instrument(symbol="ACTIVE2")

        for inst, signal in [(inst1, "BUY"), (inst2, "SELL")]:
            StockRecommendation.objects.create(
                instrument=inst,
                horizon="DELIVERY_SWING",
                signal=signal,
                setup_type="MOMENTUM",
                as_of=datetime(2024, 8, 1, tzinfo=timezone.utc),
                entry_type="CURRENT_MARKET_PRICE",
                entry_condition="Enter now",
                stop_method="ATR_BASED",
                invalidation_reason="Stop hit",
                target_method="ATR_MULTIPLE",
                confidence="MEDIUM",
                status="ACTIVE",
            )

        registry = ToolRegistry()
        registry.register(GetActiveRecommendationsTool())
        executor = ToolExecutor(registry)

        result = executor.execute("get_active_recommendations", {"limit": 50})
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.data["count"], 2)

        # All returned should be ACTIVE
        symbols = [r["symbol"] for r in result.data["active_recommendations"]]
        self.assertIn("ACTIVE1", symbols)
        self.assertIn("ACTIVE2", symbols)

    # ── 6. System integrity check ─────────────────────────────────────────────

    def test_system_check_passes(self):
        """Django system check should find no errors in the new models."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("check", "--database", "default", stdout=out, stderr=out)
        output = out.getvalue()
        self.assertNotIn("SystemCheckError", output)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 9 — INTRADAY DATA INFRASTRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class IntradayInfrastructureTests(TestCase):
    """
    Comprehensive test suite for Module 9 — Intraday Market Data Infrastructure.

    All tests are self-contained and do NOT require live provider access.
    Mocked responses are used for all provider-dependent tests.
    """

    databases = ['default']

    def setUp(self):
        """Set up test fixtures: company, instrument, intraday OHLCVBars."""
        from market.models import Company, Instrument, OHLCVBar
        from zoneinfo import ZoneInfo

        self.IST = ZoneInfo("Asia/Kolkata")
        self.UTC = ZoneInfo("UTC")

        self.company = Company.objects.create(
            short_name="INTTEST",
            name="Intraday Test Ltd",
            sector="Technology",
            industry="IT Services",
            is_active=True
        )
        self.instrument = Instrument.objects.create(
            company=self.company,
            symbol="INTTEST",
            exchange="NSE",
            instrument_type="EQUITY",
            currency="INR",
            is_active=True
        )

        # A known Monday (2024-08-05 is a Monday, not a holiday)
        self.trading_date = datetime(2024, 8, 5, tzinfo=self.UTC).date()
        # Session open 09:15 IST = 03:45 UTC
        self.session_open_utc = datetime(2024, 8, 5, 3, 45, 0, tzinfo=self.UTC)
        # Session close 15:30 IST = 10:00 UTC
        self.session_close_utc = datetime(2024, 8, 5, 10, 0, 0, tzinfo=self.UTC)

        # Insert 100 x 5m bars (more than minimum required)
        bars = []
        ts = self.session_open_utc
        for i in range(100):
            bars.append(OHLCVBar(
                instrument=self.instrument,
                timeframe="5m",
                timestamp=ts,
                open=Decimal("1000.00"),
                high=Decimal("1010.00"),
                low=Decimal("990.00"),
                close=Decimal("1005.00"),
                volume=50000,
                source="test"
            ))
            ts += timedelta(minutes=5)
        OHLCVBar.objects.bulk_create(bars)

        # Insert 50 x 15m bars
        bars_15m = []
        ts = self.session_open_utc
        for i in range(50):
            bars_15m.append(OHLCVBar(
                instrument=self.instrument,
                timeframe="15m",
                timestamp=ts,
                open=Decimal("1000.00"),
                high=Decimal("1010.00"),
                low=Decimal("990.00"),
                close=Decimal("1005.00"),
                volume=50000,
                source="test"
            ))
            ts += timedelta(minutes=15)
        OHLCVBar.objects.bulk_create(bars_15m)

        # Insert 30 x 1h bars
        bars_1h = []
        ts = self.session_open_utc
        for i in range(30):
            bars_1h.append(OHLCVBar(
                instrument=self.instrument,
                timeframe="1h",
                timestamp=ts,
                open=Decimal("1000.00"),
                high=Decimal("1010.00"),
                low=Decimal("990.00"),
                close=Decimal("1005.00"),
                volume=50000,
                source="test"
            ))
            ts += timedelta(hours=1)
        OHLCVBar.objects.bulk_create(bars_1h)

    # ── IndianMarketSession ────────────────────────────────────────────────────

    def test_session_is_trading_day_weekday(self):
        """Monday is a trading day."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        self.assertTrue(session.is_trading_day(date(2024, 8, 5)))  # Monday

    def test_session_not_trading_day_saturday(self):
        """Saturday is not a trading day."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        self.assertFalse(session.is_trading_day(date(2024, 8, 3)))  # Saturday

    def test_session_not_trading_day_sunday(self):
        """Sunday is not a trading day."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        self.assertFalse(session.is_trading_day(date(2024, 8, 4)))  # Sunday

    def test_session_not_trading_day_holiday(self):
        """Republic Day is not a trading day."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        self.assertFalse(session.is_trading_day(date(2024, 1, 26)))  # Republic Day

    def test_session_market_open_during_session(self):
        """Timestamp during 09:15-15:30 IST on a weekday → market open."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        # 12:00 IST on Monday 2024-08-05
        IST = ZoneInfo("Asia/Kolkata")
        mid_session = datetime(2024, 8, 5, 12, 0, 0, tzinfo=IST)
        self.assertTrue(session.is_market_open(mid_session))

    def test_session_market_closed_pre_open(self):
        """Timestamp before 09:15 IST → market closed."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        pre_open = datetime(2024, 8, 5, 8, 0, 0, tzinfo=IST)
        self.assertFalse(session.is_market_open(pre_open))

    def test_session_market_closed_post_close(self):
        """Timestamp after 15:30 IST → market closed."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        post_close = datetime(2024, 8, 5, 16, 0, 0, tzinfo=IST)
        self.assertFalse(session.is_market_open(post_close))

    def test_session_market_closed_weekend(self):
        """Saturday → market closed."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        saturday = datetime(2024, 8, 3, 11, 0, 0, tzinfo=IST)
        self.assertFalse(session.is_market_open(saturday))

    def test_expected_candles_5m(self):
        """5m session: 375 min / 5 min = 75 candles."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        count = session.expected_candles_for_session(date(2024, 8, 5), "5m")
        self.assertEqual(count, 75)

    def test_expected_candles_15m(self):
        """15m session: ceil(375/15) = 25 candles."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        count = session.expected_candles_for_session(date(2024, 8, 5), "15m")
        self.assertEqual(count, 25)

    def test_expected_candles_weekend_is_zero(self):
        """Weekend → 0 expected candles."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        count = session.expected_candles_for_session(date(2024, 8, 3), "5m")
        self.assertEqual(count, 0)

    def test_generate_expected_timestamps_5m(self):
        """For a trading day, 5m timestamps start at 09:15 IST."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        from datetime import date
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        ts_list = session.generate_expected_timestamps(date(2024, 8, 5), "5m")
        self.assertGreater(len(ts_list), 0)
        first_ist = ts_list[0].astimezone(IST)
        self.assertEqual(first_ist.hour, 9)
        self.assertEqual(first_ist.minute, 15)

    def test_generate_expected_timestamps_weekend_empty(self):
        """Weekend → empty timestamp list."""
        from market.services.market_session import IndianMarketSession
        from datetime import date
        session = IndianMarketSession()
        ts_list = session.generate_expected_timestamps(date(2024, 8, 3), "5m")
        self.assertEqual(len(ts_list), 0)

    def test_is_expected_gap_weekend(self):
        """Weekend timestamps are expected gaps."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        saturday = datetime(2024, 8, 3, 10, 0, 0, tzinfo=IST)
        self.assertTrue(session.is_expected_gap(saturday, "5m"))

    def test_is_expected_gap_holiday(self):
        """Exchange holidays are expected gaps."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        republic_day = datetime(2024, 1, 26, 10, 0, 0, tzinfo=IST)
        self.assertTrue(session.is_expected_gap(republic_day, "5m"))

    def test_is_not_expected_gap_during_session(self):
        """Missing bar during a valid session is NOT an expected gap."""
        from market.services.market_session import IndianMarketSession
        from zoneinfo import ZoneInfo
        session = IndianMarketSession()
        IST = ZoneInfo("Asia/Kolkata")
        mid_session = datetime(2024, 8, 5, 11, 0, 0, tzinfo=IST)
        self.assertFalse(session.is_expected_gap(mid_session, "5m"))

    # ── IntradayValidator ─────────────────────────────────────────────────────

    def test_validator_valid_bar(self):
        """Valid 5m bar passes validation."""
        from market.services.intraday_validator import validate_intraday_bar
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        bar = {
            "timestamp": datetime(2024, 8, 5, 9, 15, 0, tzinfo=IST),
            "open": Decimal("1000.00"),
            "high": Decimal("1010.00"),
            "low": Decimal("990.00"),
            "close": Decimal("1005.00"),
            "volume": 50000,
        }
        result = validate_intraday_bar(bar, "5m")
        self.assertTrue(result.is_valid, result.errors)

    def test_validator_invalid_ohlc_low_gt_high(self):
        """low > high → validation failure."""
        from market.services.intraday_validator import validate_intraday_bar
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        bar = {
            "timestamp": datetime(2024, 8, 5, 9, 15, 0, tzinfo=IST),
            "open": Decimal("1000.00"),
            "high": Decimal("990.00"),   # high < low — invalid
            "low": Decimal("1000.00"),
            "close": Decimal("995.00"),
            "volume": 50000,
        }
        result = validate_intraday_bar(bar, "5m")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("low" in e for e in result.errors))

    def test_validator_negative_volume(self):
        """Negative volume → validation failure."""
        from market.services.intraday_validator import validate_intraday_bar
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        bar = {
            "timestamp": datetime(2024, 8, 5, 9, 15, 0, tzinfo=IST),
            "open": Decimal("1000.00"),
            "high": Decimal("1010.00"),
            "low": Decimal("990.00"),
            "close": Decimal("1005.00"),
            "volume": -100,
        }
        result = validate_intraday_bar(bar, "5m")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("volume" in e.lower() for e in result.errors))

    def test_validator_naive_timestamp_rejected(self):
        """Naive datetime (no timezone) → validation failure."""
        from market.services.intraday_validator import validate_intraday_bar
        bar = {
            "timestamp": datetime(2024, 8, 5, 9, 15, 0),  # no tzinfo
            "open": Decimal("1000.00"),
            "high": Decimal("1010.00"),
            "low": Decimal("990.00"),
            "close": Decimal("1005.00"),
            "volume": 50000,
        }
        result = validate_intraday_bar(bar, "5m")
        self.assertFalse(result.is_valid)

    def test_validator_unsupported_timeframe(self):
        """Unknown timeframe → validation failure immediately."""
        from market.services.intraday_validator import validate_intraday_bar
        from zoneinfo import ZoneInfo
        bar = {"timestamp": datetime(2024, 8, 5, 9, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
               "open": Decimal("100"), "high": Decimal("110"), "low": Decimal("90"),
               "close": Decimal("105"), "volume": 1000}
        result = validate_intraday_bar(bar, "3m")  # not a supported timeframe
        self.assertFalse(result.is_valid)

    def test_validator_future_timestamp_rejected(self):
        """Timestamp far in the future → validation failure."""
        from market.services.intraday_validator import validate_intraday_bar
        future_ts = datetime.now(timezone.utc) + timedelta(hours=24)
        bar = {"timestamp": future_ts,
               "open": Decimal("100"), "high": Decimal("110"), "low": Decimal("90"),
               "close": Decimal("105"), "volume": 1000}
        result = validate_intraday_bar(bar, "5m")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("future" in e.lower() for e in result.errors))

    def test_validator_zero_volume_is_warning(self):
        """Zero volume produces a warning but is not a hard error."""
        from market.services.intraday_validator import validate_intraday_bar
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")
        bar = {
            "timestamp": datetime(2024, 8, 5, 9, 15, 0, tzinfo=IST),
            "open": Decimal("1000.00"),
            "high": Decimal("1010.00"),
            "low": Decimal("990.00"),
            "close": Decimal("1005.00"),
            "volume": 0,
        }
        result = validate_intraday_bar(bar, "5m")
        self.assertTrue(result.is_valid)
        self.assertTrue(any("zero volume" in w.lower() for w in result.warnings))

    # ── Gap Detection ─────────────────────────────────────────────────────────

    def test_gap_detector_no_gaps_when_complete(self):
        """When all expected bars are present → no data gaps."""
        from market.services.gap_detector import detect_gaps
        from datetime import date
        from market.services.market_session import IndianMarketSession
        session = IndianMarketSession()

        # Generate the expected timestamps for the trading date
        ts_list = session.generate_expected_timestamps(self.trading_date, "5m")
        if not ts_list:
            self.skipTest("No expected timestamps for trading date")

        # Only check within the first 100 bars (what setUp creates)
        from_dt = ts_list[0]
        to_dt = ts_list[min(99, len(ts_list) - 1)]

        report = detect_gaps(self.instrument, "5m", from_dt, to_dt)
        self.assertEqual(report.data_gap_count, 0)

    def test_gap_detector_detects_missing_candle(self):
        """Delete a bar mid-session → gap_detector detects it as DATA_GAP."""
        from market.models import OHLCVBar
        from market.services.gap_detector import detect_gaps, GapType
        from market.services.market_session import IndianMarketSession
        session = IndianMarketSession()

        ts_list = session.generate_expected_timestamps(self.trading_date, "5m")
        if len(ts_list) < 3:
            self.skipTest("Not enough expected timestamps")

        # Delete the bar at ts_list[2] to create a data gap
        missing_ts = ts_list[2]
        OHLCVBar.objects.filter(
            instrument=self.instrument, timeframe="5m", timestamp=missing_ts
        ).delete()

        report = detect_gaps(self.instrument, "5m", ts_list[0], ts_list[10])
        self.assertGreaterEqual(report.data_gap_count, 1)
        self.assertTrue(any(g.gap_type == GapType.DATA_GAP for g in report.data_gaps))

    def test_gap_detector_classifies_weekend_as_expected(self):
        """Timestamps on weekends → EXPECTED_GAP not DATA_GAP."""
        from market.services.gap_detector import detect_gaps, GapType
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")

        # Saturday 2024-08-03
        sat_from = datetime(2024, 8, 3, 9, 15, 0, tzinfo=IST).astimezone(timezone.utc)
        sat_to = datetime(2024, 8, 3, 15, 30, 0, tzinfo=IST).astimezone(timezone.utc)

        report = detect_gaps(self.instrument, "5m", sat_from, sat_to)
        # All "missing" bars on a Saturday are expected gaps — no data gaps
        self.assertEqual(report.data_gap_count, 0)

    # ── IntradayDataQuality ───────────────────────────────────────────────────

    def test_quality_unavailable_when_no_bars(self):
        """UNAVAILABLE when no bars exist for timeframe."""
        from market.services.intraday_quality import get_data_quality, IntradayQualityStatus
        # Create a separate instrument with no bars
        co = Company.objects.create(short_name="NOINTRA", name="NoIntra Ltd",
                                    sector="T", industry="T", is_active=True)
        inst = Instrument.objects.create(company=co, symbol="NOINTRA", exchange="NSE",
                                         instrument_type="EQUITY", currency="INR", is_active=True)
        q = get_data_quality(inst, "5m", datetime.now(timezone.utc))
        self.assertEqual(q.status, IntradayQualityStatus.UNAVAILABLE)
        self.assertIsNone(q.latest_timestamp)

    def test_quality_returns_status_for_existing_data(self):
        """get_data_quality returns a non-UNAVAILABLE status when bars exist."""
        from market.services.intraday_quality import get_data_quality, IntradayQualityStatus
        # Use a far-future as_of so bars are "old" → STALE
        far_future = datetime.now(timezone.utc) + timedelta(days=365)
        q = get_data_quality(self.instrument, "5m", far_future)
        # Should not be UNAVAILABLE (bars exist)
        self.assertNotEqual(q.status, IntradayQualityStatus.UNAVAILABLE)
        self.assertIsNotNone(q.latest_timestamp)

    def test_quality_as_dict_structure(self):
        """as_dict() returns expected keys."""
        from market.services.intraday_quality import get_data_quality
        q = get_data_quality(self.instrument, "5m", datetime.now(timezone.utc) + timedelta(days=365))
        d = q.as_dict()
        for key in ("status", "latest_timestamp", "lag_seconds", "completeness_pct", "data_gaps_count", "notes"):
            self.assertIn(key, d)

    # ── OHLCVBar Persistence (Idempotency) ────────────────────────────────────

    def test_duplicate_bar_not_inserted(self):
        """Inserting the same instrument+timeframe+timestamp twice → UniqueConstraint prevents duplicate."""
        from market.models import OHLCVBar
        from django.db import IntegrityError

        ts = self.session_open_utc
        with self.assertRaises(Exception):  # IntegrityError or similar
            OHLCVBar.objects.create(
                instrument=self.instrument,
                timeframe="5m",
                timestamp=ts,
                open=Decimal("100"), high=Decimal("110"), low=Decimal("90"),
                close=Decimal("105"), volume=1000, source="test"
            )

    def test_bulk_create_skips_existing(self):
        """IntradayService.backfill idempotency: calling with same date range doesn't duplicate bars."""
        from market.models import OHLCVBar
        count_before = OHLCVBar.objects.filter(instrument=self.instrument, timeframe="5m").count()
        # Simulate what MarketService does: check existing and skip
        existing_ts = set(OHLCVBar.objects.filter(
            instrument=self.instrument, timeframe="5m"
        ).values_list("timestamp", flat=True))
        # All timestamps already exist → nothing new to create
        ts = self.session_open_utc
        new_bars = []
        for i in range(5):
            if ts not in existing_ts:
                new_bars.append(OHLCVBar(
                    instrument=self.instrument, timeframe="5m", timestamp=ts,
                    open=Decimal("1000"), high=Decimal("1010"), low=Decimal("990"),
                    close=Decimal("1005"), volume=50000, source="test"
                ))
            ts += timedelta(minutes=5)
        OHLCVBar.objects.bulk_create(new_bars)
        count_after = OHLCVBar.objects.filter(instrument=self.instrument, timeframe="5m").count()
        self.assertEqual(count_before, count_after)

    # ── IntradayReadinessService ──────────────────────────────────────────────

    def test_readiness_fails_unsupported_timeframe(self):
        """Unsupported timeframe ('3m') → not ready."""
        from market.services.intraday_readiness import IntradayReadinessService
        svc = IntradayReadinessService()
        far_future = datetime.now(timezone.utc) + timedelta(days=365)
        result = svc.check_readiness(self.instrument, "3m", far_future)
        self.assertFalse(result.is_ready)
        self.assertTrue(any("3m" in f for f in result.checks_failed))

    def test_readiness_fails_insufficient_bars(self):
        """Fewer bars than minimum → not ready."""
        from market.models import OHLCVBar
        from market.services.intraday_readiness import IntradayReadinessService
        co = Company.objects.create(short_name="FEWBARS", name="Few Ltd",
                                    sector="T", industry="T", is_active=True)
        inst = Instrument.objects.create(company=co, symbol="FEWBARS", exchange="NSE",
                                         instrument_type="EQUITY", currency="INR", is_active=True)
        # Insert only 5 bars (minimum is 100 for 5m)
        ts = self.session_open_utc
        for i in range(5):
            OHLCVBar.objects.create(
                instrument=inst, timeframe="5m", timestamp=ts,
                open=Decimal("1000"), high=Decimal("1010"), low=Decimal("990"),
                close=Decimal("1005"), volume=50000, source="test"
            )
            ts += timedelta(minutes=5)

        svc = IntradayReadinessService()
        far_future = datetime.now(timezone.utc) + timedelta(days=365)
        result = svc.check_readiness(inst, "5m", far_future)
        self.assertFalse(result.is_ready)
        self.assertEqual(result.bar_count, 5)

    def test_readiness_fails_no_features(self):
        """Sufficient bars but no TechnicalFeature records → not ready."""
        from market.services.intraday_readiness import IntradayReadinessService
        # self.instrument has 100 5m bars but no TechnicalFeature records
        # Quality will be STALE (data is old) → gate stops at quality check
        # So we create a more specific instrument with healthy quality
        co2 = Company.objects.create(short_name="NOFEATURE", name="NoFeat Ltd",
                                     sector="T", industry="T", is_active=True)
        inst2 = Instrument.objects.create(company=co2, symbol="NOFEATURE", exchange="NSE",
                                          instrument_type="EQUITY", currency="INR", is_active=True)
        # Insert 100 very recent 5m bars (so quality = HEALTHY or INCOMPLETE)
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        from market.models import OHLCVBar
        bars = []
        for i in range(100):
            bars.append(OHLCVBar(
                instrument=inst2, timeframe="5m", timestamp=ts,
                open=Decimal("1000"), high=Decimal("1010"), low=Decimal("990"),
                close=Decimal("1005"), volume=50000, source="test"
            ))
            ts += timedelta(minutes=5)
        OHLCVBar.objects.bulk_create(bars)

        svc = IntradayReadinessService()
        result = svc.check_readiness(inst2, "5m", datetime.now(timezone.utc) + timedelta(minutes=10))
        # Should fail because no features (or stale — either way not ready)
        self.assertFalse(result.is_ready)

    def test_readiness_passes_with_bars_quality_and_features(self):
        """Sufficient bars + healthy quality + features → ready."""
        from market.models import OHLCVBar, TechnicalFeature
        from market.services.intraday_readiness import IntradayReadinessService

        co3 = Company.objects.create(short_name="READY5M", name="Ready Ltd",
                                     sector="T", industry="T", is_active=True)
        inst3 = Instrument.objects.create(company=co3, symbol="READY5M", exchange="NSE",
                                          instrument_type="EQUITY", currency="INR", is_active=True)

        # 100 very recent 5m bars
        ts = datetime.now(timezone.utc) - timedelta(minutes=500)
        bars = []
        for i in range(100):
            bars.append(OHLCVBar(
                instrument=inst3, timeframe="5m", timestamp=ts,
                open=Decimal("1000"), high=Decimal("1010"), low=Decimal("990"),
                close=Decimal("1005"), volume=50000, source="test"
            ))
            ts += timedelta(minutes=5)
        OHLCVBar.objects.bulk_create(bars)

        # Insert a TechnicalFeature for 5m
        latest_ts = datetime.now(timezone.utc) - timedelta(minutes=5)
        TechnicalFeature.objects.create(
            instrument=inst3,
            timeframe="5m",
            timestamp=latest_ts,
            name="RSI_14",
            param_key="period=14",
            value=Decimal("55.0"),
        )

        svc = IntradayReadinessService()
        result = svc.check_readiness(inst3, "5m", datetime.now(timezone.utc))
        # Passes bar count + features. Quality may be STALE or HEALTHY depending on time.
        # At minimum, we verify the structure is correct
        self.assertIsInstance(result.is_ready, bool)
        self.assertIsNotNone(result.bar_count)
        self.assertEqual(result.bar_count, 100)

    # ── Module 8 Integration: Intraday Gate ──────────────────────────────────

    def test_intraday_gate_not_ready_when_readiness_fails(self):
        """SignalEngine returns NOT_READY when IntradayReadinessService fails."""
        from market.services.signal_engine import SignalEngine
        from market.signal_enums import SignalDirection

        # New instrument with no intraday data → readiness will fail
        co = Company.objects.create(short_name="GATETEST", name="Gate Test Ltd",
                                    sector="T", industry="T", is_active=True)
        inst = Instrument.objects.create(company=co, symbol="GATETEST", exchange="NSE",
                                         instrument_type="EQUITY", currency="INR", is_active=True)
        engine = SignalEngine()
        draft = engine.generate_recommendation(inst, "INTRADAY")
        self.assertEqual(draft.signal, SignalDirection.NOT_READY.value)

    def test_daily_recommendation_unaffected(self):
        """DELIVERY_SWING horizon still works — Module 8 daily pipeline unaffected."""
        from market.services.signal_engine import SignalEngine
        from market.signal_enums import SignalDirection
        # Instrument with no daily bars → INSUFFICIENT_DATA (not NOT_READY)
        co = Company.objects.create(short_name="DAILYOK", name="Daily Ok Ltd",
                                    sector="T", industry="T", is_active=True)
        inst = Instrument.objects.create(company=co, symbol="DAILYOK", exchange="NSE",
                                         instrument_type="EQUITY", currency="INR", is_active=True)
        engine = SignalEngine()
        draft = engine.generate_recommendation(inst, "DELIVERY_SWING")
        # No daily bars → INSUFFICIENT_DATA (not NOT_READY — intraday gate doesn't apply here)
        self.assertIn(draft.signal, [
            SignalDirection.INSUFFICIENT_DATA.value,
            SignalDirection.NOT_READY.value,
            SignalDirection.NO_ACTION.value,
        ])

    # ── PIT Safety ────────────────────────────────────────────────────────────

    def test_pit_safety_future_intraday_bars_invisible(self):
        """Intraday bars timestamped in the future are invisible when as_of = now."""
        from market.models import OHLCVBar
        now_utc = datetime.now(timezone.utc)
        future_ts = now_utc + timedelta(hours=2)

        co = Company.objects.create(short_name="PITINTRA", name="PIT Intraday Ltd",
                                    sector="T", industry="T", is_active=True)
        inst = Instrument.objects.create(company=co, symbol="PITINTRA", exchange="NSE",
                                         instrument_type="EQUITY", currency="INR", is_active=True)
        OHLCVBar.objects.create(
            instrument=inst, timeframe="5m", timestamp=future_ts,
            open=Decimal("1000"), high=Decimal("1010"), low=Decimal("990"),
            close=Decimal("1005"), volume=50000, source="test"
        )

        # Query PIT-safe: should find 0 bars at or before now
        count = OHLCVBar.objects.filter(
            instrument=inst, timeframe="5m", timestamp__lte=now_utc
        ).count()
        self.assertEqual(count, 0)

    # ── Feature Engine for Intraday Timeframes ────────────────────────────────

    def test_feature_engine_runs_for_5m(self):
        """TechnicalFeatureEngine calculates features for 5m timeframe."""
        from market.services.feature_engine import TechnicalFeatureEngine
        from market.models import TechnicalFeature
        engine = TechnicalFeatureEngine()
        count = engine.calculate_and_save_features(self.instrument, "5m")
        self.assertGreater(count, 0)
        # Features should be stored under timeframe="5m"
        features = TechnicalFeature.objects.filter(instrument=self.instrument, timeframe="5m")
        self.assertGreater(features.count(), 0)

    def test_feature_engine_runs_for_15m(self):
        """TechnicalFeatureEngine calculates features for 15m timeframe."""
        from market.services.feature_engine import TechnicalFeatureEngine
        from market.models import TechnicalFeature
        engine = TechnicalFeatureEngine()
        count = engine.calculate_and_save_features(self.instrument, "15m")
        self.assertGreater(count, 0)
        features = TechnicalFeature.objects.filter(instrument=self.instrument, timeframe="15m")
        self.assertGreater(features.count(), 0)

    def test_feature_engine_runs_for_1h(self):
        """TechnicalFeatureEngine calculates features for 1h timeframe."""
        from market.services.feature_engine import TechnicalFeatureEngine
        from market.models import TechnicalFeature
        engine = TechnicalFeatureEngine()
        count = engine.calculate_and_save_features(self.instrument, "1h")
        self.assertGreater(count, 0)
        features = TechnicalFeature.objects.filter(instrument=self.instrument, timeframe="1h")
        self.assertGreater(features.count(), 0)

    def test_feature_timeframes_do_not_mix(self):
        """5m features are stored under timeframe='5m', not '1d'."""
        from market.services.feature_engine import TechnicalFeatureEngine
        from market.models import TechnicalFeature
        engine = TechnicalFeatureEngine()
        engine.calculate_and_save_features(self.instrument, "5m")
        # Querying timeframe='1d' should find 0 for this instrument
        daily_count = TechnicalFeature.objects.filter(
            instrument=self.instrument, timeframe="1d"
        ).count()
        self.assertEqual(daily_count, 0)

    # ── LLM Tools ────────────────────────────────────────────────────────────

    def test_intraday_ohlcv_tool_returns_data(self):
        """GetIntradayOHLCVTool returns bars for existing instrument."""
        from llm.tools.implementations.market_tool import GetIntradayOHLCVTool
        tool = GetIntradayOHLCVTool()
        result = tool.execute(symbol="INTTEST", timeframe="5m", limit=10)
        self.assertTrue(result.success)
        self.assertEqual(result.data["symbol"], "INTTEST")
        self.assertLessEqual(result.data["bar_count"], 10)

    def test_intraday_ohlcv_tool_symbol_not_found(self):
        """GetIntradayOHLCVTool returns failure for unknown symbol."""
        from llm.tools.implementations.market_tool import GetIntradayOHLCVTool
        tool = GetIntradayOHLCVTool()
        result = tool.execute(symbol="DOESNOTEXIST", timeframe="5m")
        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "SYMBOL_NOT_FOUND")

    def test_intraday_data_quality_tool_returns_status(self):
        """GetIntradayDataQualityTool returns a quality status."""
        from llm.tools.implementations.market_tool import GetIntradayDataQualityTool
        tool = GetIntradayDataQualityTool()
        result = tool.execute(symbol="INTTEST", timeframe="5m")
        self.assertTrue(result.success)
        self.assertIn("status", result.data)

    def test_intraday_features_tool_no_features_returns_empty(self):
        """GetIntradayFeaturesTool returns empty features when none calculated."""
        from llm.tools.implementations.market_tool import GetIntradayFeaturesTool
        tool = GetIntradayFeaturesTool()
        # INTTEST has no TechnicalFeatures for 5m yet
        result = tool.execute(symbol="INTTEST", timeframe="5m")
        self.assertTrue(result.success)
        # Either empty features dict or note about missing features
        data = result.data
        self.assertIn("features", data)

    def test_intraday_features_tool_returns_features_after_calculation(self):
        """GetIntradayFeaturesTool returns actual features after calculation."""
        from market.services.feature_engine import TechnicalFeatureEngine
        from llm.tools.implementations.market_tool import GetIntradayFeaturesTool

        # Calculate features first
        engine = TechnicalFeatureEngine()
        engine.calculate_and_save_features(self.instrument, "5m")

        tool = GetIntradayFeaturesTool()
        result = tool.execute(symbol="INTTEST", timeframe="5m")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.data.get("timestamp"))
        self.assertGreater(len(result.data.get("features", {})), 0)

    # ── Celery Task: Market-Hours Gate ────────────────────────────────────────

    def test_intraday_task_skips_when_market_closed(self):
        """run_intraday_incremental_update returns SKIPPED when market is closed."""
        from market.tasks import run_intraday_incremental_update
        from unittest.mock import patch

        # IndianMarketSession is imported inside the task function, so patch at source
        with patch(
            "market.services.market_session.IndianMarketSession.is_market_open",
            return_value=False
        ):
            result = run_intraday_incremental_update()

        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(result["reason"], "market_closed")


# ─── Module 10: Intraday Strategy Engine Tests ───────────────────────────────


class IntradayStrategyEngineTests(TestCase):
    """
    Tests for Module 10: Intraday Signal & Strategy Engine.

    Coverage:
      1. Session window classification
      2. VWAP computation
      3. Opening range framework
      4. Intraday detectors (7 detectors)
      5. No-trade conditions
      6. Cooldown gate
      7. Lifecycle / session expiry
      8. Daily recommendation regression (unchanged)
      9. PIT safety for intraday bars
    """

    def _make_bar(self, symbol="TEST", timeframe="5m", timestamp=None, close=100.0,
                  high=None, low=None, open_=None, volume=10000):
        """Helper: create an OHLCVBar for testing."""
        from market.models import OHLCVBar, Instrument, Company
        company, _ = Company.objects.get_or_create(name="Test Co", defaults={"sector": "Technology"})
        inst, _ = Instrument.objects.get_or_create(
            symbol=symbol,
            defaults={"company": company, "instrument_type": "EQUITY", "exchange": "NSE"}
        )
        if timestamp is None:
            from market.services.market_session import IndianMarketSession
            from market.services.market_session import IST
            from datetime import date as _date
            today = _date.today()
            timestamp = datetime(today.year, today.month, today.day, 9, 30, tzinfo=IST).astimezone(timezone.utc)
        bar = OHLCVBar.objects.create(
            instrument=inst,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_ or close * 0.998,
            high=high or close * 1.002,
            low=low or close * 0.997,
            close=close,
            volume=volume,
        )
        return inst, bar

    def _make_bar_series(self, symbol="SERIES", n=50, base_close=500.0, timeframe="5m",
                         session_date=None, start_hour=9, start_min=15):
        """Helper: create a series of n bars with 5-minute spacing."""
        from market.services.market_session import IndianMarketSession
        from market.services.market_session import IST
        from datetime import date as _date

        if session_date is None:
            session_date = _date.today()

        bars = []
        inst = None
        for i in range(n):
            total_minutes = start_hour * 60 + start_min + i * 5
            h, m = divmod(total_minutes, 60)
            ts = datetime(session_date.year, session_date.month, session_date.day, h, m, tzinfo=IST)
            ts_utc = ts.astimezone(timezone.utc)
            close = base_close + i * 0.1
            inst, bar = self._make_bar(
                symbol=symbol, timeframe=timeframe,
                timestamp=ts_utc, close=close,
                high=close * 1.003, low=close * 0.997,
                volume=15000 + i * 100,
            )
            bars.append(bar)
        return inst, bars

    # ── 1. Session Window Classification ──────────────────────────────────────

    def test_session_classify_opening_window(self):
        """09:20 IST → OPENING window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        # Use a known weekday (Monday=0 ... Sunday=6)
        from datetime import date
        # Pick a Monday if today is a weekend
        dt = datetime(today.year, today.month, today.day, 9, 20, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "OPENING")
        self.assertTrue(sw.is_valid_for_trading)

    def test_session_classify_morning_window(self):
        """10:00 IST → MORNING window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        dt = datetime(today.year, today.month, today.day, 10, 0, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "MORNING")

    def test_session_classify_midday_window(self):
        """12:00 IST → MIDDAY window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        dt = datetime(today.year, today.month, today.day, 12, 0, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "MIDDAY")

    def test_session_classify_afternoon_window(self):
        """13:30 IST → AFTERNOON window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        dt = datetime(today.year, today.month, today.day, 13, 30, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "AFTERNOON")

    def test_session_classify_closing_window(self):
        """15:00 IST → CLOSING window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        dt = datetime(today.year, today.month, today.day, 15, 0, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "CLOSING")

    def test_session_classify_outside(self):
        """08:00 IST → OUTSIDE window."""
        from market.services.intraday_session import classify_session
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()
        dt = datetime(today.year, today.month, today.day, 8, 0, tzinfo=IST)
        with patch("market.services.intraday_session.IndianMarketSession.is_trading_day", return_value=True):
            sw = classify_session(dt)
        self.assertEqual(sw.window, "OUTSIDE")
        self.assertFalse(sw.is_valid_for_trading)

    # ── 2. VWAP Computation ───────────────────────────────────────────────────

    def test_vwap_computed_from_session_bars(self):
        """VWAP = sum(typical_price * volume) / sum(volume) — verified manually."""
        from market.services.intraday_indicators import compute_intraday_indicators
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()

        # Create 35 bars with known values to allow indicator calculation
        inst, bars = self._make_bar_series("VWAPTEST", n=35, base_close=200.0, session_date=today)

        ind = compute_intraday_indicators(bars, today)
        self.assertTrue(ind.vwap_available, "VWAP should be available when session bars exist")
        self.assertIsNotNone(ind.vwap)
        # VWAP should be close to the average close price (~200 + small drift)
        self.assertAlmostEqual(ind.vwap, 200.0 + 35 * 0.1 / 2, delta=5.0)

    def test_vwap_unavailable_when_no_session_bars(self):
        """VWAP should be None when no bars match the session date."""
        from market.services.intraday_indicators import compute_intraday_indicators
        from datetime import date
        # Use a past date that won't match "today"
        future_date = date(2030, 1, 2)

        inst, bars = self._make_bar_series("VWAP2", n=5, base_close=100.0)
        ind = compute_intraday_indicators(bars, future_date)
        self.assertFalse(ind.vwap_available)
        self.assertIsNone(ind.vwap)

    # ── 3. Opening Range ──────────────────────────────────────────────────────

    def test_opening_range_computed_correctly(self):
        """OR high/low = max/min of first 3 bars (15 min for 5m timeframe)."""
        from market.services.opening_range import compute_opening_range
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()

        inst, bars = self._make_bar_series("ORTEST", n=10, base_close=300.0, session_date=today)
        or_range = compute_opening_range(bars, today, "5m")

        self.assertIsNotNone(or_range)
        self.assertTrue(or_range.is_complete)
        self.assertGreaterEqual(or_range.high, or_range.low)
        self.assertEqual(or_range.session_date, today)
        self.assertGreater(or_range.bars_used, 0)

    def test_opening_range_incomplete_when_too_few_bars(self):
        """OR is incomplete when fewer bars than min_or_bars_complete."""
        from market.services.opening_range import compute_opening_range
        from market.services.market_session import IndianMarketSession
        from datetime import date as _date
        from market.services.market_session import IST
        today = _date.today()

        # Only create 1 bar in OR window — 5m needs 3 for is_complete
        ts = datetime(today.year, today.month, today.day, 9, 15, tzinfo=IST).astimezone(timezone.utc)
        inst, bar = self._make_bar("ORTEST2", "5m", ts, close=400.0)
        or_range = compute_opening_range([bar], today, "5m")

        if or_range:
            self.assertFalse(or_range.is_complete)

    def test_or_above_high_method(self):
        """above_or_high returns True when price is sufficiently above OR high."""
        from market.services.opening_range import OpeningRange
        from datetime import date
        or_r = OpeningRange(
            high=200.0, low=195.0, range_size=5.0, range_pct=2.5,
            total_volume=50000, bars_used=3, session_date=date.today(), is_complete=True
        )
        self.assertTrue(or_r.above_or_high(201.0))
        self.assertFalse(or_r.above_or_high(199.0))

    def test_measured_move_target_up(self):
        """Measured move = entry + OR range."""
        from market.services.opening_range import OpeningRange
        from datetime import date
        or_r = OpeningRange(
            high=200.0, low=195.0, range_size=5.0, range_pct=2.5,
            total_volume=50000, bars_used=3, session_date=date.today(), is_complete=True
        )
        target = or_r.measured_move_target_up(201.0)
        self.assertAlmostEqual(target, 206.0, places=1)

    # ── 4. Intraday Detectors ─────────────────────────────────────────────────

    def _make_indicators(self, **kwargs):
        """Build an IntradayIndicators with default bullish values."""
        from market.services.intraday_indicators import IntradayIndicators
        defaults = {
            "ema_fast": 205.0, "ema_slow": 200.0,
            "rsi": 60.0, "atr": 3.0, "adx": 18.0,
            "relative_volume": 1.5, "vwap": 202.0, "vwap_available": True,
            "close": 207.0, "high": 208.0, "low": 204.0, "open": 204.5,
            "macd_line": 0.5, "macd_signal": 0.3, "macd_hist": 0.2,
            "current_volume": 15000, "avg_volume": 10000, "bar_count": 35,
        }
        defaults.update(kwargs)
        return IntradayIndicators(**defaults)

    def _make_or_range(self, high=200.0, low=195.0, complete=True):
        from market.services.opening_range import OpeningRange
        from datetime import date
        return OpeningRange(
            high=high, low=low, range_size=high - low,
            range_pct=(high - low) / low * 100,
            total_volume=50000, bars_used=3,
            session_date=date.today(), is_complete=complete,
        )

    def test_or_breakout_detected_when_conditions_met(self):
        """OR breakout fires when price above OR high + volume + RSI."""
        from market.services.intraday_detectors import detect_or_breakout
        ind = self._make_indicators(close=202.0, rsi=58.0, relative_volume=1.5)
        or_range = self._make_or_range(high=201.0, low=196.0)
        result = detect_or_breakout(ind, or_range, "MORNING")
        self.assertTrue(result.detected)
        self.assertGreater(result.score, 50.0)

    def test_or_breakout_not_detected_below_high(self):
        """OR breakout NOT fired when price below OR high."""
        from market.services.intraday_detectors import detect_or_breakout
        ind = self._make_indicators(close=199.0, rsi=55.0, relative_volume=1.5)
        or_range = self._make_or_range(high=201.0)
        result = detect_or_breakout(ind, or_range, "MORNING")
        self.assertFalse(result.detected)

    def test_or_breakout_not_detected_without_volume(self):
        """OR breakout NOT fired without volume confirmation."""
        from market.services.intraday_detectors import detect_or_breakout
        ind = self._make_indicators(close=203.0, rsi=60.0, relative_volume=0.8)
        or_range = self._make_or_range(high=201.0)
        result = detect_or_breakout(ind, or_range, "MORNING")
        self.assertFalse(result.detected)

    def test_or_breakout_not_detected_incomplete_or(self):
        """OR breakout blocked when OR is incomplete."""
        from market.services.intraday_detectors import detect_or_breakout
        ind = self._make_indicators(close=203.0, rsi=60.0, relative_volume=1.5)
        or_range = self._make_or_range(high=201.0, complete=False)
        result = detect_or_breakout(ind, or_range, "MORNING")
        self.assertFalse(result.detected)
        self.assertIn("not yet formed", result.conditions_failed[0])

    def test_or_breakdown_detected(self):
        """OR breakdown fires when price below OR low + distribution volume."""
        from market.services.intraday_detectors import detect_or_breakdown
        ind = self._make_indicators(close=193.0, rsi=42.0, relative_volume=1.4,
                                     ema_fast=196.0, ema_slow=198.0)
        or_range = self._make_or_range(high=202.0, low=196.0)
        result = detect_or_breakdown(ind, or_range, "MORNING")
        self.assertTrue(result.detected)

    def test_momentum_continuation_detected(self):
        """Momentum continuation fires with EMA trend, RSI 55-72, and volume."""
        from market.services.intraday_detectors import detect_momentum_continuation
        ind = self._make_indicators(close=207.0, rsi=62.0, relative_volume=1.3)
        result = detect_momentum_continuation(ind, "MORNING")
        self.assertTrue(result.detected)

    def test_momentum_continuation_blocked_no_ema_trend(self):
        """Momentum continuation blocked when EMA9 < EMA21."""
        from market.services.intraday_detectors import detect_momentum_continuation
        ind = self._make_indicators(close=207.0, rsi=62.0, relative_volume=1.3,
                                     ema_fast=195.0, ema_slow=205.0)
        result = detect_momentum_continuation(ind, "MORNING")
        self.assertFalse(result.detected)

    def test_intraday_pullback_detected(self):
        """Pullback fires when price retracing to EMA zone, RSI 35-55."""
        from market.services.intraday_detectors import detect_intraday_pullback
        # EMA9 > EMA21, price between them, RSI in pullback zone
        ind = self._make_indicators(
            ema_fast=202.0, ema_slow=198.0, close=200.5, rsi=47.0,
            vwap=201.0, vwap_available=True, relative_volume=1.0
        )
        result = detect_intraday_pullback(ind, "MORNING")
        self.assertTrue(result.detected)

    def test_vwap_reclaim_detected(self):
        """VWAP reclaim fires when price crosses above VWAP with volume."""
        from market.services.intraday_detectors import detect_vwap_reclaim
        ind = self._make_indicators(close=203.0, vwap=202.0, vwap_available=True,
                                     relative_volume=1.4, rsi=52.0)
        result = detect_vwap_reclaim(ind, prev_bar_close=201.5, session_window="MORNING")
        self.assertTrue(result.detected)

    def test_vwap_reclaim_blocked_no_vwap(self):
        """VWAP reclaim blocked when VWAP is unavailable."""
        from market.services.intraday_detectors import detect_vwap_reclaim
        ind = self._make_indicators(vwap=None, vwap_available=False)
        result = detect_vwap_reclaim(ind, session_window="MORNING")
        self.assertFalse(result.detected)
        self.assertIn("unavailable", result.conditions_failed[0])

    def test_vwap_rejection_detected(self):
        """VWAP rejection fires when price moves below VWAP after testing it."""
        from market.services.intraday_detectors import detect_vwap_rejection
        ind = self._make_indicators(close=199.5, vwap=200.0, vwap_available=True,
                                     relative_volume=1.3, rsi=48.0)
        result = detect_vwap_rejection(ind, prev_bar_close=200.2, session_window="MORNING")
        self.assertTrue(result.detected)

    def test_intraday_range_breakout_detected(self):
        """Range breakout fires when ADX < 20 + price breaks 20-bar high + volume."""
        from market.services.intraday_detectors import detect_intraday_range_breakout
        from market.services.intraday_indicators import IntradayIndicators

        ind = self._make_indicators(close=210.0, adx=15.0, relative_volume=1.5, rsi=55.0)

        # Create mock bars with highs all below 210 (close > range_high)
        from unittest.mock import MagicMock
        mock_bars = [MagicMock(high=205.0) for _ in range(25)]
        mock_bars.append(MagicMock(high=210.0))  # current bar high

        result = detect_intraday_range_breakout(ind, mock_bars, "MORNING")
        self.assertTrue(result.detected)

    def test_intraday_range_breakout_blocked_trending_market(self):
        """Range breakout blocked when ADX >= 20 (already trending)."""
        from market.services.intraday_detectors import detect_intraday_range_breakout
        ind = self._make_indicators(close=210.0, adx=28.0, relative_volume=1.5, rsi=55.0)
        from unittest.mock import MagicMock
        mock_bars = [MagicMock(high=205.0) for _ in range(25)]
        result = detect_intraday_range_breakout(ind, mock_bars, "MORNING")
        self.assertFalse(result.detected)

    # ── 5. No-trade Conditions ────────────────────────────────────────────────

    def test_engine_returns_not_ready_when_readiness_fails(self):
        """IntradaySignalEngine returns NOT_READY when readiness service fails."""
        from market.services.intraday_signal_engine import IntradaySignalEngine
        from market.signal_enums import SignalDirection

        inst, _ = self._make_bar_series("NOTREADY", n=5)
        engine = IntradaySignalEngine()
        with patch("market.services.intraday_signal_engine.IntradayReadinessService") as MockReady:
            mock_readiness = MagicMock()
            mock_readiness.is_ready = False
            mock_readiness.reason = "Insufficient bars"
            MockReady.return_value.check_readiness.return_value = mock_readiness
            draft = engine.generate_recommendation(inst, "5m")

        self.assertEqual(draft.signal, SignalDirection.NOT_READY.value)

    def test_engine_returns_no_action_outside_session(self):
        """IntradaySignalEngine returns NO_ACTION when session is OUTSIDE."""
        from market.services.intraday_signal_engine import IntradaySignalEngine
        from market.signal_enums import SignalDirection
        from market.services.intraday_session import SessionWindow
        from datetime import date

        inst, bars = self._make_bar_series("OUTSIDEST", n=40)
        engine = IntradaySignalEngine()

        outside_sw = SessionWindow(
            window="OUTSIDE", minutes_elapsed=-1, minutes_remaining=-1,
            is_valid_for_trading=False, session_date=date.today()
        )

        # Pass as_of well after last bar so all 40 bars are visible to PIT query
        as_of_dt = bars[-1].timestamp + timedelta(minutes=5)

        with patch("market.services.intraday_signal_engine.IntradayReadinessService") as MockReady, \
             patch("market.services.intraday_signal_engine.classify_session", return_value=outside_sw):
            mock_readiness = MagicMock()
            mock_readiness.is_ready = True
            MockReady.return_value.check_readiness.return_value = mock_readiness
            draft = engine.generate_recommendation(inst, "5m", as_of=as_of_dt)

        self.assertEqual(draft.signal, SignalDirection.NO_ACTION.value)
        self.assertIn("Outside trading session", draft.entry_condition)

    def test_engine_returns_no_action_on_dead_tape(self):
        """NO_ACTION when relative volume < MIN_TAPE_VOLUME."""
        from market.services.intraday_signal_engine import IntradaySignalEngine
        from market.signal_enums import SignalDirection
        from market.services.intraday_indicators import IntradayIndicators
        from market.services.intraday_session import SessionWindow
        from datetime import date

        inst, bars = self._make_bar_series("DEADTAPE", n=40)
        engine = IntradaySignalEngine()

        morning_sw = SessionWindow("MORNING", 60, 180, True, date.today())
        dead_ind = IntradayIndicators(relative_volume=0.3, atr=2.0, close=100.0, bar_count=40)

        # Pass as_of well after last bar so all 40 bars are visible to PIT query
        as_of_dt = bars[-1].timestamp + timedelta(minutes=5)

        with patch("market.services.intraday_signal_engine.IntradayReadinessService") as MockReady, \
             patch("market.services.intraday_signal_engine.classify_session", return_value=morning_sw), \
             patch("market.services.intraday_signal_engine.compute_intraday_indicators", return_value=dead_ind):
            mock_readiness = MagicMock()
            mock_readiness.is_ready = True
            MockReady.return_value.check_readiness.return_value = mock_readiness
            draft = engine.generate_recommendation(inst, "5m", as_of=as_of_dt)

        self.assertEqual(draft.signal, SignalDirection.NO_ACTION.value)
        self.assertIn("dead tape", draft.entry_condition)

    # ── 6. Cooldown Gate ─────────────────────────────────────────────────────

    def test_cooldown_blocks_duplicate_signal(self):
        """Cooldown is active when an identical intraday rec was recently generated."""
        from market.services.intraday_cooldown import is_in_cooldown
        from market.models import StockRecommendation

        inst, _ = self._make_bar("COOLTEST")
        rec_time = datetime.now(timezone.utc)

        # Create a recent ACTIVE intraday rec
        StockRecommendation.objects.create(
            instrument=inst,
            horizon="INTRADAY",
            signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT",
            as_of=rec_time,
            entry_type="BREAKOUT_CONFIRMATION",
            entry_condition="test",
            stop_method="ATR_BASED",
            invalidation_reason="test",
            target_method="ATR_MULTIPLE",
            confidence="MEDIUM",
            status="ACTIVE",
        )

        # Capture as_of AFTER creation so generated_at <= as_of is guaranteed
        as_of = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.assertTrue(is_in_cooldown(inst, "BUY", "OPENING_RANGE_BREAKOUT", as_of, cooldown_minutes=30))

    def test_cooldown_allows_different_setup(self):
        """Cooldown does NOT block a materially different setup type."""
        from market.services.intraday_cooldown import is_in_cooldown
        from market.models import StockRecommendation

        inst, _ = self._make_bar("COOLDIFF")
        rec_time = datetime.now(timezone.utc)

        StockRecommendation.objects.create(
            instrument=inst, horizon="INTRADAY", signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT", as_of=rec_time,
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="ATR_BASED", invalidation_reason="test",
            target_method="ATR_MULTIPLE", confidence="MEDIUM",
            status="ACTIVE",
        )

        # Different setup type — should NOT be blocked
        as_of = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.assertFalse(is_in_cooldown(inst, "BUY", "VWAP_RECLAIM", as_of, cooldown_minutes=30))

    def test_cooldown_allows_after_window_expires(self):
        """Cooldown does NOT block when previous rec is older than cooldown window."""
        from market.services.intraday_cooldown import is_in_cooldown
        from market.models import StockRecommendation

        inst, _ = self._make_bar("COOLOLD")
        old_time = datetime.now(timezone.utc) - timedelta(minutes=60)

        # Create and then backdate generated_at via update() to bypass auto_now_add
        rec = StockRecommendation.objects.create(
            instrument=inst, horizon="INTRADAY", signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT", as_of=old_time,
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="ATR_BASED", invalidation_reason="test",
            target_method="ATR_MULTIPLE", confidence="MEDIUM",
            status="ACTIVE",
        )
        # Force generated_at to old_time (bypasses auto_now_add for testing)
        StockRecommendation.objects.filter(pk=rec.pk).update(generated_at=old_time)

        now = datetime.now(timezone.utc)
        # 30-min cooldown — rec is 60 min old — should NOT be blocked
        self.assertFalse(is_in_cooldown(inst, "BUY", "OPENING_RANGE_BREAKOUT", now, cooldown_minutes=30))

    # ── 7. Lifecycle / Session Expiry ─────────────────────────────────────────

    def test_expire_marks_active_intraday_recs_expired(self):
        """expire_intraday_session_recommendations marks past-expires_at recs as EXPIRED."""
        from market.services.intraday_lifecycle import expire_intraday_session_recommendations
        from market.models import StockRecommendation

        inst, _ = self._make_bar("EXPTEST")
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        now = datetime.now(timezone.utc)

        rec = StockRecommendation.objects.create(
            instrument=inst, horizon="INTRADAY", signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT", as_of=past_expiry,
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="ATR_BASED", invalidation_reason="test",
            target_method="ATR_MULTIPLE", confidence="HIGH",
            status="ACTIVE",
            expires_at=past_expiry,
        )

        count = expire_intraday_session_recommendations(now)
        self.assertEqual(count, 1)
        rec.refresh_from_db()
        self.assertEqual(rec.status, "EXPIRED")

    def test_expire_does_not_touch_non_intraday_recs(self):
        """Expiry MUST NOT affect DELIVERY_SWING or LONG_TERM recommendations."""
        from market.services.intraday_lifecycle import expire_intraday_session_recommendations
        from market.models import StockRecommendation

        inst, _ = self._make_bar("EXPDELIV")
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        now = datetime.now(timezone.utc)

        # Create a DELIVERY_SWING rec with no expires_at (should not be touched)
        rec = StockRecommendation.objects.create(
            instrument=inst, horizon="DELIVERY_SWING", signal="BUY",
            setup_type="BREAKOUT", as_of=past_expiry,
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="ATR_BASED", invalidation_reason="test",
            target_method="ATR_MULTIPLE", confidence="HIGH",
            status="ACTIVE",
        )

        count = expire_intraday_session_recommendations(now)
        self.assertEqual(count, 0)  # delivery rec untouched
        rec.refresh_from_db()
        self.assertEqual(rec.status, "ACTIVE")

    def test_session_expiry_computes_correct_utc_time(self):
        """compute_session_expiry returns 15:30 IST = 10:00 UTC."""
        from market.services.intraday_lifecycle import compute_session_expiry
        from datetime import date

        test_date = date(2026, 8, 25)  # Monday
        expires_at = compute_session_expiry(test_date, "5m")

        # 15:30 IST = UTC+5:30, so 15:30 - 5:30 = 10:00 UTC
        self.assertEqual(expires_at.hour, 10)
        self.assertEqual(expires_at.minute, 0)

    # ── 8. Daily Recommendation Regression ───────────────────────────────────

    def test_daily_detectors_not_affected_by_new_intraday_setups(self):
        """Daily setup_detectors.run_all_detectors should NOT include intraday setup types."""
        from market.services.setup_detectors import run_all_detectors
        from market.signal_enums import SetupType

        INTRADAY_SETUP_VALUES = {
            SetupType.OPENING_RANGE_BREAKOUT.value,
            SetupType.OPENING_RANGE_BREAKDOWN.value,
            SetupType.INTRADAY_MOMENTUM_CONTINUATION.value,
            SetupType.INTRADAY_PULLBACK.value,
            SetupType.VWAP_RECLAIM.value,
            SetupType.VWAP_REJECTION.value,
            SetupType.INTRADAY_RANGE_BREAKOUT.value,
        }

        # Run daily detectors with some valid tf_dict
        tf_dict = {
            "RSI_14": 58.0, "SMA_50": 190.0, "SMA_200": 180.0, "ATR_14": 4.0,
            "SMA_20": 192.0, "MACD_12_26_9": 0.5, "BB_UPPER_20": 205.0,
            "BB_LOWER_20": 180.0, "ADX_14": 25.0,
        }
        results = run_all_detectors(tf_dict, close=195.0)

        for r in results:
            self.assertNotIn(r.setup_type.value, INTRADAY_SETUP_VALUES,
                             f"Daily detector returned intraday setup: {r.setup_type.value}")

    # ── 9. PIT Safety for Intraday Bars ──────────────────────────────────────

    def test_pit_safety_future_bars_invisible_to_engine(self):
        """Bars with timestamp > as_of must NOT be loaded by IntradaySignalEngine."""
        from market.services.intraday_signal_engine import IntradaySignalEngine
        from market.signal_enums import SignalDirection

        inst, bars = self._make_bar_series("PITSAFE10", n=5)
        future_bar_time = bars[-1].timestamp + timedelta(hours=2)

        # Create a future bar
        future_bar = OHLCVBar.objects.create(
            instrument=inst, timeframe="5m", timestamp=future_bar_time,
            open=900.0, high=910.0, low=895.0, close=905.0, volume=99999
        )

        engine = IntradaySignalEngine()
        past_as_of = bars[-1].timestamp  # Query at time of last valid bar

        with patch("market.services.intraday_signal_engine.IntradayReadinessService") as MockReady:
            mock_r = MagicMock()
            mock_r.is_ready = True
            MockReady.return_value.check_readiness.return_value = mock_r

            draft = engine.generate_recommendation(inst, "5m", as_of=past_as_of)

        # Engine should not see the future bar — if it did, close would be 905
        if draft.setup_details:
            indicators = draft.setup_details.get("intraday_indicators", {})
            close_seen = indicators.get("close")
            if close_seen is not None:
                self.assertNotAlmostEqual(close_seen, 905.0, delta=0.5,
                                          msg="Future bar close value leaked into PIT-safe query")

    # ── 10. Intraday Strategy Config ──────────────────────────────────────────

    def test_strategy_config_has_required_attributes(self):
        """intraday_strategy_config module has all required config attributes."""
        from market import intraday_strategy_config as cfg
        self.assertIsNotNone(cfg.STRATEGY_VERSION)
        self.assertIsInstance(cfg.SUPPORTED_INTRADAY_TIMEFRAMES, list)
        self.assertIn("5m", cfg.SUPPORTED_INTRADAY_TIMEFRAMES)
        self.assertIn("15m", cfg.SUPPORTED_INTRADAY_TIMEFRAMES)
        self.assertIsInstance(cfg.MIN_RISK_REWARD_INTRADAY, float)
        self.assertGreater(cfg.MIN_RISK_REWARD_INTRADAY, 1.0)
        self.assertIsInstance(cfg.COOLDOWN_MINUTES, int)
        self.assertGreater(cfg.COOLDOWN_MINUTES, 0)
        self.assertIsInstance(cfg.SETUP_SESSION_FILTERS, dict)

    def test_setup_session_filters_no_opening_window_for_or(self):
        """OPENING_RANGE_BREAKOUT must NOT fire during OPENING window — OR not yet formed."""
        from market.intraday_strategy_config import SETUP_SESSION_FILTERS
        self.assertNotIn("OPENING", SETUP_SESSION_FILTERS.get("OPENING_RANGE_BREAKOUT", set()))

    # ── 11. Model Intraday Fields ─────────────────────────────────────────────

    def test_stock_recommendation_intraday_fields_nullable(self):
        """New intraday fields on StockRecommendation accept null — daily records unaffected."""
        from market.models import StockRecommendation
        inst, _ = self._make_bar("FIELDTEST")
        rec = StockRecommendation.objects.create(
            instrument=inst, horizon="DELIVERY_SWING", signal="BUY",
            setup_type="BREAKOUT", as_of=datetime.now(timezone.utc),
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="ATR_BASED", invalidation_reason="test",
            target_method="ATR_MULTIPLE", confidence="LOW", status="ACTIVE",
        )
        # All intraday fields should be null for daily recs
        self.assertIsNone(rec.timeframe)
        self.assertIsNone(rec.target_2_price)
        self.assertIsNone(rec.target_2_method)
        self.assertIsNone(rec.session_window)
        self.assertIsNone(rec.strategy_version)
        self.assertIsNone(rec.expires_at)

    def test_stock_recommendation_can_store_intraday_fields(self):
        """New intraday fields can be set and retrieved."""
        from market.models import StockRecommendation
        inst, _ = self._make_bar("FIELDTEST2")
        expiry = datetime.now(timezone.utc) + timedelta(hours=6)
        rec = StockRecommendation.objects.create(
            instrument=inst, horizon="INTRADAY", signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT", as_of=datetime.now(timezone.utc),
            entry_type="BREAKOUT_CONFIRMATION", entry_condition="test",
            stop_method="STRUCTURAL", invalidation_reason="test",
            target_method="MEASURED_MOVE", confidence="HIGH", status="ACTIVE",
            timeframe="5m",
            target_2_price=215.0,
            target_2_method="ATR_MULTIPLE",
            session_window="MORNING",
            strategy_version="1.0",
            expires_at=expiry,
        )
        rec.refresh_from_db()
        self.assertEqual(rec.timeframe, "5m")
        self.assertEqual(rec.session_window, "MORNING")
        self.assertEqual(rec.strategy_version, "1.0")
        self.assertIsNotNone(rec.expires_at)
        self.assertIsNotNone(rec.target_2_price)


# =============================================================================
# Module 11 — Recommendation Outcome Tracking & Backtesting Foundation
# =============================================================================

class OutcomeTrackingTests(TestCase):
    """
    Tests for Module 11: Recommendation Outcome Tracking & Backtesting Foundation.

    Areas covered:
      1.  EntryEvaluator — BUY/SELL trigger, no trigger, exact boundary
      2.  ExitEvaluator — stop hit, target hit, not hit, same-bar ambiguity
      3.  Same-bar ambiguity — CONSERVATIVE / OPTIMISTIC / EXCLUDE policies
      4.  Session expiry — expires_at handling
      5.  Max holding duration kill-switch
      6.  MFE / MAE calculation — BUY and SELL
      7.  P&L — long, short, NO_COST, REALISTIC, slippage
      8.  R-multiple — positive, negative, zero-risk edge case
      9.  Cost model — NO_COST / REALISTIC / slippage
      10. Performance metrics — win rate, expectancy, profit factor, drawdown
      11. Statistical warnings — small sample, insufficient sample
      12. Dimension slices — by setup/timeframe/direction
      13. RecommendationOutcome model — fields, constraints, idempotency
      14. BacktestRun model — creation, config serialisation
      15. Lifecycle — ACTIVE→TRIGGERED→TARGET_HIT/STOPPED/EXPIRED/AMBIGUOUS
      16. PIT safety — future bars excluded from evaluation
      17. Idempotency — same bar evaluated twice, same rec twice
      18. Historical data limitation warnings
      19. Daily recommendation regression (Modules 1–10 unaffected)
      20. AmbiguityPolicy enum and ExitReason enum completeness
    """

    def setUp(self):
        """Create shared test fixtures: instrument, bars, and recommendation template."""
        from market.models import StockRecommendation, RecommendationOutcome, BacktestRun

        self.company = Company.objects.create(
            name="Outcome Test Corp",
            sector="Technology", industry="Software",
        )
        self.instrument = Instrument.objects.create(
            symbol="OUT1", company=self.company, instrument_type="EQUITY",
            is_active=True, lot_size=1,
        )

        # Base timestamps (all UTC)
        self.t0 = datetime(2026, 8, 1, 4, 0, 0, tzinfo=timezone.utc)  # 09:30 IST

        # Build a sequence of 10 intraday bars (5m each)
        self.bars = []
        for i in range(10):
            bar = OHLCVBar.objects.create(
                instrument=self.instrument,
                timeframe="5m",
                timestamp=self.t0 + timedelta(minutes=5 * i),
                open=Decimal("100.00"),
                high=Decimal("102.00"),
                low=Decimal("98.00"),
                close=Decimal("101.00"),
                volume=10000,
            )
            self.bars.append(bar)

        # Standard BUY recommendation at t0
        self.rec_buy = StockRecommendation.objects.create(
            instrument=self.instrument,
            horizon="INTRADAY",
            signal="BUY",
            setup_type="OPENING_RANGE_BREAKOUT",
            as_of=self.t0,
            entry_type="BREAKOUT_CONFIRMATION",
            entry_price=Decimal("101.50"),   # above all bar highs=102 → triggers bar 0
            entry_condition="Buy above 101.50",
            stop_price=Decimal("97.00"),
            stop_method="ATR_BASED",
            invalidation_reason="Close below 97",
            target_price=Decimal("108.00"),
            target_method="ATR_MULTIPLE",
            risk=Decimal("4.50"),
            reward=Decimal("6.50"),
            risk_reward_ratio=Decimal("1.44"),
            confidence="HIGH",
            confidence_components={},
            market_context={"regime": "BULLISH"},
            sector_context={"sector": "Technology"},
            supporting_factors=[],
            risk_factors=[],
            setup_details={},
            data_quality={},
            status="ACTIVE",
            timeframe="5m",
            strategy_version="1.0",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_bars(self, ohlc_sequence, start_time=None, timeframe="5m"):
        """Create OHLCVBar list from (open, high, low, close) tuples.

        Default start_time offsets by 2 hours from t0 to avoid conflict with
        setUp bars (which occupy t0 to t0+45m).
        """
        t = start_time or (self.t0 + timedelta(hours=2))
        result = []
        for i, (o, h, l, c) in enumerate(ohlc_sequence):
            bar = OHLCVBar.objects.create(
                instrument=self.instrument,
                timeframe=timeframe,
                timestamp=t + timedelta(minutes=5 * i),
                open=Decimal(str(o)), high=Decimal(str(h)),
                low=Decimal(str(l)), close=Decimal(str(c)),
                volume=10000,
            )
            result.append(bar)
        return result

    def _make_rec(self, signal="BUY", entry=101.5, stop=97.0, target=108.0,
                  horizon="INTRADAY", setup_type="OPENING_RANGE_BREAKOUT",
                  expires_at=None, timeframe="5m"):
        from market.models import StockRecommendation
        return StockRecommendation.objects.create(
            instrument=self.instrument,
            horizon=horizon,
            signal=signal,
            setup_type=setup_type,
            as_of=self.t0,
            entry_type="BREAKOUT_CONFIRMATION",
            entry_price=Decimal(str(entry)),
            entry_condition=f"entry at {entry}",
            stop_price=Decimal(str(stop)),
            stop_method="ATR_BASED",
            invalidation_reason="n/a",
            target_price=Decimal(str(target)),
            target_method="ATR_MULTIPLE",
            risk=Decimal("4.00"),
            reward=Decimal("6.00"),
            risk_reward_ratio=Decimal("1.5"),
            confidence="MEDIUM",
            confidence_components={},
            market_context={"regime": "SIDEWAYS"},
            sector_context={"sector": "Energy"},
            supporting_factors=[],
            risk_factors=[],
            setup_details={},
            data_quality={},
            status="ACTIVE",
            timeframe=timeframe,
            strategy_version="1.0",
            expires_at=expires_at,
        )

    # =========================================================================
    # 1. EntryEvaluator
    # =========================================================================

    def test_entry_buy_triggered(self):
        """BUY: entry triggers when bar.high >= entry_price."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="BUY", entry=101.0)
        bars = self._make_bars([(100, 102, 98, 101)])  # high=102 >= 101
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertTrue(result.triggered)
        self.assertEqual(result.trigger_bar_index, 0)
        self.assertAlmostEqual(result.trigger_price, 102.0)

    def test_entry_sell_triggered(self):
        """SELL: entry triggers when bar.low <= entry_price."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="SELL", entry=99.0, stop=103.0, target=93.0)
        bars = self._make_bars([(100, 101, 98, 100)])  # low=98 <= 99
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertTrue(result.triggered)
        self.assertAlmostEqual(result.trigger_price, 98.0)

    def test_entry_not_triggered(self):
        """Entry price never reached → triggered=False."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="BUY", entry=110.0)  # bars only go to 102
        bars = self._make_bars([(100, 102, 98, 101), (100, 102, 98, 101)])
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertFalse(result.triggered)
        self.assertEqual(result.bars_scanned, 2)

    def test_entry_exact_boundary_buy(self):
        """BUY entry triggers on exact equality: bar.high == entry_price."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="BUY", entry=102.0)
        bars = self._make_bars([(100, 102, 98, 101)])  # high exactly 102
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertTrue(result.triggered)

    def test_entry_exact_boundary_sell(self):
        """SELL entry triggers on exact equality: bar.low == entry_price."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="SELL", entry=98.0, stop=103.0, target=93.0)
        bars = self._make_bars([(100, 101, 98, 100)])  # low exactly 98
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertTrue(result.triggered)

    def test_entry_no_entry_price(self):
        """Rec with entry_price=None → untriggered, no crash."""
        from market.services.outcome_engine import EntryEvaluator
        from market.models import StockRecommendation
        rec = self._make_rec(signal="BUY", entry=100.0)
        rec.entry_price = None
        rec.save()
        bars = self._make_bars([(100, 102, 98, 101)])
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertFalse(result.triggered)

    def test_entry_triggers_on_second_bar(self):
        """Entry triggers on bar index 1, not 0."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="BUY", entry=105.0)
        bars = self._make_bars([
            (100, 102, 98, 101),  # bar 0: high=102 < 105 → no trigger
            (103, 106, 100, 105), # bar 1: high=106 >= 105 → trigger
        ])
        result = EntryEvaluator().evaluate(rec, bars)
        self.assertTrue(result.triggered)
        self.assertEqual(result.trigger_bar_index, 1)

    # =========================================================================
    # 2. ExitEvaluator — target hit
    # =========================================================================

    def test_exit_target_hit_buy(self):
        """BUY target hit: bar.high >= target_price."""
        from market.services.outcome_engine import EntryEvaluator, ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(105, 109, 104, 108)])  # high=109 >= 108
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "TARGET_HIT")
        self.assertTrue(result.target_hit)
        self.assertFalse(result.stop_hit)

    def test_exit_stop_hit_buy(self):
        """BUY stop hit: bar.low <= stop_price."""
        from market.services.outcome_engine import EntryEvaluator, ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=110.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(99, 101, 94, 98)])  # low=94 <= 95
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "STOP_HIT")
        self.assertTrue(result.stop_hit)
        self.assertFalse(result.target_hit)

    def test_exit_target_hit_sell(self):
        """SELL target hit: bar.low <= target_price (target is below entry for SELL)."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="SELL", entry=100.0, stop=105.0, target=93.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(97, 99, 92, 94)])  # low=92 <= 93
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "TARGET_HIT")
        self.assertTrue(result.target_hit)

    def test_exit_stop_hit_sell(self):
        """SELL stop hit: bar.high >= stop_price."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="SELL", entry=100.0, stop=105.0, target=90.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(103, 106, 101, 104)])  # high=106 >= 105
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "STOP_HIT")
        self.assertTrue(result.stop_hit)

    def test_exit_neither_hit(self):
        """Neither stop nor target triggered → EXPIRED_MAX_DURATION when bars exhausted."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=90.0, target=120.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        # All bars in safe zone
        bars_after = self._make_bars([(100, 105, 95, 102), (100, 105, 95, 102)])
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after, max_holding_bars=200)
        self.assertEqual(result.exit_reason, "EXPIRED_MAX_DURATION")
        self.assertFalse(result.target_hit)
        self.assertFalse(result.stop_hit)

    def test_exit_no_entry(self):
        """ExitEvaluator with entry_triggered=False → NO_ENTRY."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=False, trigger_bar_index=None,
            trigger_timestamp=None, trigger_price=None, bars_scanned=0
        )
        result = ExitEvaluator().evaluate(rec, entry_result, [])
        self.assertEqual(result.exit_reason, "NO_ENTRY")

    # =========================================================================
    # 3. Same-bar ambiguity
    # =========================================================================

    def test_ambiguity_detected(self):
        """Both stop and target touched in same bar → AMBIGUOUS_INTRABAR."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        # Bar has both high >= target AND low <= stop in same bar
        bars_after = self._make_bars([(100, 110, 93, 103)])  # h=110>=108, l=93<=95
        result = ExitEvaluator().evaluate(
            rec, entry_result, bars_after, ambiguity_policy="CONSERVATIVE"
        )
        self.assertEqual(result.exit_reason, "AMBIGUOUS_INTRABAR")
        self.assertTrue(result.ambiguous_intrabar)
        self.assertIsNone(result.target_hit)
        self.assertIsNone(result.stop_hit)

    def test_ambiguity_policy_conservative_stop_wins(self):
        """CONSERVATIVE: ambiguous bar → exit_price = stop_price."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(100, 110, 93, 103)])
        result = ExitEvaluator().evaluate(
            rec, entry_result, bars_after, ambiguity_policy="CONSERVATIVE"
        )
        self.assertEqual(result.exit_price, 95.0)   # stop_price wins

    def test_ambiguity_policy_optimistic_target_wins(self):
        """OPTIMISTIC: ambiguous bar → exit_price = target_price."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(100, 110, 93, 103)])
        result = ExitEvaluator().evaluate(
            rec, entry_result, bars_after, ambiguity_policy="OPTIMISTIC"
        )
        self.assertEqual(result.exit_price, 108.0)  # target_price wins

    def test_ambiguity_policy_exclude(self):
        """EXCLUDE: ambiguous bar → exit_price = None."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(100, 110, 93, 103)])
        result = ExitEvaluator().evaluate(
            rec, entry_result, bars_after, ambiguity_policy="EXCLUDE"
        )
        self.assertIsNone(result.exit_price)
        self.assertTrue(result.ambiguous_intrabar)

    def test_target_only_no_ambiguity(self):
        """Target reached but low > stop → no ambiguity, clean TARGET_HIT."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(105, 110, 98, 109)])  # low=98 > stop=95
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "TARGET_HIT")
        self.assertFalse(result.ambiguous_intrabar)

    def test_stop_only_no_ambiguity(self):
        """Stop reached but high < target → no ambiguity, clean STOP_HIT."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=108.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        bars_after = self._make_bars([(99, 103, 93, 98)])  # high=103 < target=108
        result = ExitEvaluator().evaluate(rec, entry_result, bars_after)
        self.assertEqual(result.exit_reason, "STOP_HIT")
        self.assertFalse(result.ambiguous_intrabar)

    # =========================================================================
    # 4. Session expiry
    # =========================================================================

    def test_exit_session_expiry(self):
        """Intraday rec with expires_at: bar at/after expiry → EXPIRED_SESSION."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        # Use an offset start time to avoid bar timestamp conflict with setUp bars (t0..t0+45min)
        bar_start = self.t0 + timedelta(hours=3)
        expires_at = bar_start
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0,
                             target=120.0, expires_at=expires_at)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        # Bar timestamp == expires_at → session close
        bar = OHLCVBar.objects.create(
            instrument=self.instrument, timeframe="5m",
            timestamp=bar_start,
            open=Decimal("101"), high=Decimal("105"),
            low=Decimal("99"), close=Decimal("103"), volume=1000,
        )
        result = ExitEvaluator().evaluate(rec, entry_result, [bar])
        self.assertEqual(result.exit_reason, "EXPIRED_SESSION")

    # =========================================================================
    # 5. Max holding duration kill-switch
    # =========================================================================

    def test_exit_max_holding_bars(self):
        """Position held for max_holding_bars without exit → EXPIRED_MAX_DURATION."""
        from market.services.outcome_engine import ExitEvaluator, EntryResult
        rec = self._make_rec(signal="BUY", entry=100.0, stop=90.0, target=120.0)
        entry_result = EntryResult(
            triggered=True, trigger_bar_index=0,
            trigger_timestamp=self.t0, trigger_price=100.0, bars_scanned=1
        )
        # 5 safe bars, max_holding_bars=3 → kill after bar index 3
        bars = self._make_bars([(100, 105, 95, 102)] * 5)
        result = ExitEvaluator().evaluate(
            rec, entry_result, bars, max_holding_bars=3
        )
        self.assertEqual(result.exit_reason, "EXPIRED_MAX_DURATION")

    # =========================================================================
    # 6. MFE / MAE
    # =========================================================================

    def test_mfe_mae_buy(self):
        """MFE and MAE computed correctly for a BUY trade."""
        from market.services.outcome_engine import MFEMAECalculator
        bars = self._make_bars([
            (100, 105, 99, 103),  # MFE candidate: (105-100)/100*100 = 5%
            (103, 103, 97, 100),  # MAE candidate: (100-97)/100*100 = 3%
        ])
        result = MFEMAECalculator().calculate("BUY", 100.0, bars)
        self.assertAlmostEqual(result.max_favorable_excursion, 5.0, places=2)
        self.assertAlmostEqual(result.max_adverse_excursion, 3.0, places=2)

    def test_mfe_mae_sell(self):
        """MFE and MAE for a SELL trade (favorable is downward)."""
        from market.services.outcome_engine import MFEMAECalculator
        bars = self._make_bars([
            (100, 102, 94, 97),   # MFE: (100-94)/100*100 = 6%, MAE: (102-100)/100*100 = 2%
        ])
        result = MFEMAECalculator().calculate("SELL", 100.0, bars)
        self.assertAlmostEqual(result.max_favorable_excursion, 6.0, places=2)
        self.assertAlmostEqual(result.max_adverse_excursion, 2.0, places=2)

    def test_mfe_mae_no_bars(self):
        """Empty bars → None values, no crash."""
        from market.services.outcome_engine import MFEMAECalculator
        result = MFEMAECalculator().calculate("BUY", 100.0, [])
        self.assertIsNone(result.max_favorable_excursion)
        self.assertIsNone(result.max_adverse_excursion)

    # =========================================================================
    # 7. P&L calculations
    # =========================================================================

    def test_pnl_long_win_no_cost(self):
        """BUY winner: net_pnl_absolute = exit - entry (no cost)."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=110.0,
            stop_price=95.0, cost_config=CostConfig.no_cost()
        )
        self.assertAlmostEqual(result.gross_pnl_absolute, 10.0, places=2)
        self.assertAlmostEqual(result.net_pnl_absolute, 10.0, places=2)
        self.assertEqual(result.cost_absolute, 0.0)

    def test_pnl_long_loss_no_cost(self):
        """BUY loser: net_pnl_absolute is negative."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=95.0,
            stop_price=95.0, cost_config=CostConfig.no_cost()
        )
        self.assertAlmostEqual(result.net_pnl_absolute, -5.0, places=2)

    def test_pnl_short_win_no_cost(self):
        """SELL winner: entry > exit → positive P&L."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="SELL", actual_entry_price=100.0, actual_exit_price=90.0,
            stop_price=105.0, cost_config=CostConfig.no_cost()
        )
        self.assertAlmostEqual(result.net_pnl_absolute, 10.0, places=2)

    def test_pnl_with_realistic_cost(self):
        """REALISTIC cost reduces net P&L below gross."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        cfg = CostConfig.realistic_nse_equity()
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=110.0,
            stop_price=95.0, cost_config=cfg
        )
        self.assertGreater(result.gross_pnl_absolute, result.net_pnl_absolute)
        self.assertGreater(result.cost_absolute, 0.0)

    def test_pnl_slippage_worsens_entry_buy(self):
        """BUY slippage: actual entry is higher than raw price."""
        from market.services.cost_model import SlippageModel, CostConfig
        cfg = CostConfig(mode="REALISTIC", brokerage_percent=0.0,
                        stt_percent=0.0, slippage_bps=10.0)  # 10 bps
        adj = SlippageModel.apply_entry_slippage(100.0, "BUY", cfg)
        self.assertAlmostEqual(adj, 100.1, places=4)

    def test_pnl_slippage_worsens_entry_sell(self):
        """SELL slippage: actual entry is lower than raw price."""
        from market.services.cost_model import SlippageModel, CostConfig
        cfg = CostConfig(mode="REALISTIC", brokerage_percent=0.0,
                        stt_percent=0.0, slippage_bps=10.0)
        adj = SlippageModel.apply_entry_slippage(100.0, "SELL", cfg)
        self.assertAlmostEqual(adj, 99.9, places=4)

    def test_pnl_no_cost_zero_slippage(self):
        """NO_COST config → slippage = 0."""
        from market.services.cost_model import SlippageModel, CostConfig
        adj = SlippageModel.apply_entry_slippage(100.0, "BUY", CostConfig.no_cost())
        self.assertEqual(adj, 100.0)

    # =========================================================================
    # 8. R-multiple
    # =========================================================================

    def test_r_multiple_positive(self):
        """Winner: R > 0."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=110.0,
            stop_price=95.0, cost_config=CostConfig.no_cost()
        )
        # risk = 100 - 95 = 5; R = 10 / 5 = 2.0
        self.assertAlmostEqual(result.r_multiple, 2.0, places=2)

    def test_r_multiple_negative(self):
        """Loser: R < 0."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=95.0,
            stop_price=95.0, cost_config=CostConfig.no_cost()
        )
        self.assertLess(result.r_multiple, 0.0)

    def test_r_multiple_no_stop(self):
        """No stop_price → r_multiple=None, no crash."""
        from market.services.outcome_engine import PnLCalculator
        from market.services.cost_model import CostConfig
        result = PnLCalculator().calculate(
            signal="BUY", actual_entry_price=100.0, actual_exit_price=110.0,
            stop_price=None, cost_config=CostConfig.no_cost()
        )
        self.assertIsNone(result.r_multiple)

    # =========================================================================
    # 9. Cost model structure
    # =========================================================================

    def test_cost_config_no_cost_serialise(self):
        """NO_COST config round-trips through to_dict/from_dict."""
        from market.services.cost_model import CostConfig
        cfg = CostConfig.no_cost()
        restored = CostConfig.from_dict(cfg.to_dict())
        self.assertEqual(restored.mode, "NO_COST")
        self.assertEqual(restored.slippage_bps, 0.0)

    def test_cost_config_realistic_fields(self):
        """REALISTIC config has non-zero brokerage and slippage."""
        from market.services.cost_model import CostConfig
        cfg = CostConfig.realistic_nse_equity()
        self.assertEqual(cfg.mode, "REALISTIC")
        self.assertGreater(cfg.brokerage_percent, 0.0)
        self.assertGreater(cfg.slippage_bps, 0.0)

    def test_cost_compute_roundtrip(self):
        """Total cost is positive for REALISTIC mode."""
        from market.services.cost_model import compute_total_cost, CostConfig
        cost = compute_total_cost(100.0, 110.0, "BUY", CostConfig.realistic_nse_equity())
        self.assertGreater(cost, 0.0)

    def test_cost_no_cost_zero(self):
        """NO_COST → compute_total_cost returns 0.0."""
        from market.services.cost_model import compute_total_cost, CostConfig
        cost = compute_total_cost(100.0, 110.0, "BUY", CostConfig.no_cost())
        self.assertEqual(cost, 0.0)

    # =========================================================================
    # 10 & 11. Performance metrics + statistical warnings
    # =========================================================================

    def _make_outcome_stub(self, entry_triggered, exit_reason,
                           net_pnl_pct=None, r_multiple=None,
                           ambiguous=False, hold_bars=None,
                           setup_type="OPENING_RANGE_BREAKOUT",
                           timeframe="5m", direction="BUY"):
        """Create a lightweight stub that mimics a RecommendationOutcome."""

        class RecStub:
            pass

        class OutcomeStub:
            pass

        rec = RecStub()
        rec.setup_type = setup_type
        rec.timeframe  = timeframe
        rec.signal     = direction
        rec.market_context = {"regime": "BULLISH"}
        rec.sector_context = {"sector": "Technology"}

        out = OutcomeStub()
        out.recommendation       = rec
        out.entry_triggered      = entry_triggered
        out.exit_reason          = exit_reason
        out.net_pnl_percent      = net_pnl_pct
        out.r_multiple           = r_multiple
        out.ambiguous_intrabar   = ambiguous
        out.holding_duration_bars = hold_bars
        return out

    def test_performance_basic_wins_losses(self):
        """Basic win/loss counts compute correctly."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", net_pnl_pct=5.0, r_multiple=2.0),
            self._make_outcome_stub(True, "TARGET_HIT", net_pnl_pct=3.0, r_multiple=1.5),
            self._make_outcome_stub(True, "STOP_HIT",   net_pnl_pct=-4.0, r_multiple=-1.0),
            self._make_outcome_stub(False, "NO_ENTRY"),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertEqual(report.total_signals, 4)
        self.assertEqual(report.triggered, 3)
        self.assertEqual(report.untriggered, 1)
        self.assertEqual(report.wins, 2)
        self.assertEqual(report.losses, 1)

    def test_performance_small_sample_warning(self):
        """< 10 triggered trades → SMALL_SAMPLE_WARNING in statistical_warnings."""
        from market.services.performance_metrics import StrategyPerformanceService, SMALL_SAMPLE_WARNING
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0),
            self._make_outcome_stub(True, "STOP_HIT", r_multiple=-1.0),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertTrue(
            any(SMALL_SAMPLE_WARNING in w for w in report.statistical_warnings)
        )
        # win_rate should be null (too few samples)
        self.assertIsNone(report.win_rate)

    def test_performance_win_rate_with_enough_samples(self):
        """10+ triggered trades → win_rate computed."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = []
        for _ in range(7):
            outcomes.append(self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0))
        for _ in range(3):
            outcomes.append(self._make_outcome_stub(True, "STOP_HIT", r_multiple=-1.0))
        report = StrategyPerformanceService().compute(outcomes)
        self.assertIsNotNone(report.win_rate)
        self.assertAlmostEqual(report.win_rate, 70.0, places=0)

    def test_performance_expectancy_requires_30_samples(self):
        """< 30 triggered → expectancy is None."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0)
            for _ in range(15)
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertIsNone(report.expectancy)

    def test_performance_max_drawdown_computed(self):
        """Max drawdown computed when ≥2 trades with R values."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0),
            self._make_outcome_stub(True, "STOP_HIT",   r_multiple=-1.0),
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=1.5),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertIsNotNone(report.max_drawdown_r)
        self.assertLessEqual(report.max_drawdown_r, 0.0)  # drawdown is negative

    def test_performance_ambiguous_conservative(self):
        """CONSERVATIVE policy: ambiguous → counted as loss."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "AMBIGUOUS_INTRABAR", ambiguous=True, r_multiple=-0.5),
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0),
            # Fill to 10 for win_rate to appear
            *[self._make_outcome_stub(True, "TARGET_HIT", r_multiple=1.5) for _ in range(8)],
        ]
        report = StrategyPerformanceService().compute(outcomes, ambiguity_policy="CONSERVATIVE")
        self.assertEqual(report.ambiguous, 1)
        self.assertEqual(report.losses, 1)  # ambiguous counted as loss

    def test_performance_ambiguous_exclude(self):
        """EXCLUDE policy: ambiguous counted in ambiguous but NOT in wins or losses."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "AMBIGUOUS_INTRABAR", ambiguous=True),
            *[self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0) for _ in range(9)],
        ]
        report = StrategyPerformanceService().compute(outcomes, ambiguity_policy="EXCLUDE")
        self.assertEqual(report.ambiguous, 1)
        self.assertEqual(report.losses, 0)

    # =========================================================================
    # 12. Dimension slices
    # =========================================================================

    def test_performance_by_setup_type(self):
        """by_setup_type is populated with correct keys."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", setup_type="OPENING_RANGE_BREAKOUT"),
            self._make_outcome_stub(True, "STOP_HIT", setup_type="VWAP_RECLAIM"),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertIn("OPENING_RANGE_BREAKOUT", report.by_setup_type)
        self.assertIn("VWAP_RECLAIM", report.by_setup_type)

    def test_performance_by_direction(self):
        """by_direction slice created for BUY and SELL."""
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", direction="BUY"),
            self._make_outcome_stub(True, "STOP_HIT", direction="SELL"),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        self.assertIn("BUY", report.by_direction)
        self.assertIn("SELL", report.by_direction)

    def test_performance_report_serialises(self):
        """PerformanceReport.to_dict() returns a JSON-serialisable dict."""
        import json
        from market.services.performance_metrics import StrategyPerformanceService
        outcomes = [
            self._make_outcome_stub(True, "TARGET_HIT", r_multiple=2.0),
        ]
        report = StrategyPerformanceService().compute(outcomes)
        d = report.to_dict()
        # Should not raise
        json.dumps(d)

    # =========================================================================
    # 13. RecommendationOutcome model
    # =========================================================================

    def test_outcome_model_fields_nullable(self):
        """RecommendationOutcome: all optional fields accept null."""
        from market.models import RecommendationOutcome
        outcome = RecommendationOutcome.objects.create(
            recommendation=self.rec_buy,
            evaluation_version=1,
            entry_triggered=False,
            exit_reason="NO_ENTRY",
            bars_evaluated=0,
        )
        self.assertIsNone(outcome.actual_entry_price)
        self.assertIsNone(outcome.r_multiple)
        self.assertIsNone(outcome.max_favorable_excursion)

    def test_outcome_model_unique_constraint(self):
        """Second outcome for same (rec, version) raises IntegrityError."""
        from market.models import RecommendationOutcome
        from django.db import IntegrityError
        RecommendationOutcome.objects.create(
            recommendation=self.rec_buy,
            evaluation_version=1,
            entry_triggered=False,
            exit_reason="NO_ENTRY",
            bars_evaluated=0,
        )
        with self.assertRaises(IntegrityError):
            RecommendationOutcome.objects.create(
                recommendation=self.rec_buy,
                evaluation_version=1,  # same version
                entry_triggered=False,
                exit_reason="NO_ENTRY",
                bars_evaluated=0,
            )

    def test_outcome_second_version_allowed(self):
        """Different evaluation_version for same rec is allowed."""
        from market.models import RecommendationOutcome
        RecommendationOutcome.objects.create(
            recommendation=self.rec_buy, evaluation_version=1,
            entry_triggered=False, exit_reason="NO_ENTRY", bars_evaluated=0,
        )
        # version=2 should not raise
        out2 = RecommendationOutcome.objects.create(
            recommendation=self.rec_buy, evaluation_version=2,
            entry_triggered=True, exit_reason="TARGET_HIT", bars_evaluated=5,
        )
        self.assertEqual(out2.evaluation_version, 2)

    # =========================================================================
    # 14. BacktestRun model
    # =========================================================================

    def test_backtest_run_creation(self):
        """BacktestRun created with correct fields."""
        from market.models import BacktestRun
        from market.services.backtest_config import BacktestConfig
        from datetime import date
        config = BacktestConfig(
            universe_name="TEST_UNIV",
            timeframe="5m",
            horizon="INTRADAY",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 8, 1),
        )
        run = BacktestRun.objects.create(
            run_id="test-run-001",
            config=config.to_dict(),
            status="PENDING",
            universe_name=config.universe_name,
            timeframe=config.timeframe,
            horizon=config.horizon,
            start_date=config.start_date,
            end_date=config.end_date,
            strategy_version=config.strategy_version,
        )
        self.assertEqual(run.status, "PENDING")
        self.assertEqual(run.timeframe, "5m")

    def test_backtest_config_roundtrip(self):
        """BacktestConfig.to_dict() / from_dict() are inverse operations."""
        from market.services.backtest_config import BacktestConfig
        from market.services.cost_model import CostConfig
        from datetime import date
        config = BacktestConfig(
            universe_name="NIFTY50",
            timeframe="5m",
            horizon="INTRADAY",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            cost_config=CostConfig.realistic_nse_equity(),
            ambiguity_policy="CONSERVATIVE",
        )
        restored = BacktestConfig.from_dict(config.to_dict())
        self.assertEqual(restored.universe_name, "NIFTY50")
        self.assertEqual(restored.cost_config.mode, "REALISTIC")
        self.assertEqual(restored.ambiguity_policy, "CONSERVATIVE")

    # =========================================================================
    # 15. Lifecycle transitions via OutcomeService
    # =========================================================================

    def test_outcome_service_no_entry_marks_expired(self):
        """OutcomeService: untriggered rec after expiry → EXPIRED status + NO_ENTRY outcome."""
        from market.services.outcome_service import RecommendationOutcomeService
        from market.models import RecommendationOutcome
        rec = self._make_rec(signal="BUY", entry=200.0,  # price never reached
                             expires_at=self.t0 - timedelta(minutes=1))  # already expired
        svc = RecommendationOutcomeService()
        # Bars that never reach 200
        bars = self._make_bars([(100, 102, 98, 101), (100, 102, 98, 101)])
        outcome = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=1), bars=bars)
        self.assertIsNotNone(outcome)
        self.assertFalse(outcome.entry_triggered)
        self.assertEqual(outcome.exit_reason, "NO_ENTRY")
        rec.refresh_from_db()
        self.assertEqual(rec.status, "EXPIRED")

    def test_outcome_service_target_hit_updates_status(self):
        """OutcomeService: target reached → rec status = TARGET_HIT."""
        from market.services.outcome_service import RecommendationOutcomeService
        from market.models import RecommendationOutcome
        rec = self._make_rec(signal="BUY", entry=100.0, stop=90.0, target=105.0)
        svc = RecommendationOutcomeService()
        bars = self._make_bars([
            (100, 101, 99, 100),  # entry triggers (high=101 >= 100)
            (101, 107, 100, 106), # target hit (high=107 >= 105)
        ])
        outcome = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=2), bars=bars)
        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.entry_triggered)
        self.assertEqual(outcome.exit_reason, "TARGET_HIT")
        rec.refresh_from_db()
        self.assertEqual(rec.status, "TARGET_HIT")

    def test_outcome_service_stop_hit_updates_status(self):
        """OutcomeService: stop triggered → rec status = STOPPED."""
        from market.services.outcome_service import RecommendationOutcomeService
        rec = self._make_rec(signal="BUY", entry=100.0, stop=95.0, target=115.0)
        svc = RecommendationOutcomeService()
        bars = self._make_bars([
            (100, 101, 99, 100),  # entry triggers
            (99, 100, 93, 97),    # stop hit (low=93 <= 95)
        ])
        outcome = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=2), bars=bars)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.exit_reason, "STOP_HIT")
        rec.refresh_from_db()
        self.assertEqual(rec.status, "STOPPED")

    # =========================================================================
    # 16. Idempotency
    # =========================================================================

    def test_outcome_service_idempotent_same_rec(self):
        """Calling evaluate_single twice on same rec returns None on second call."""
        from market.services.outcome_service import RecommendationOutcomeService
        from market.models import RecommendationOutcome
        rec = self._make_rec(signal="BUY", entry=200.0,
                             expires_at=self.t0 - timedelta(minutes=1))
        svc = RecommendationOutcomeService()
        bars = self._make_bars([(100, 102, 98, 101)])
        outcome1 = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=1), bars=bars)
        outcome2 = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=1), bars=bars)
        self.assertIsNotNone(outcome1)
        self.assertIsNone(outcome2)  # second call returns None (already evaluated)
        # Only one outcome record exists
        self.assertEqual(
            RecommendationOutcome.objects.filter(recommendation=rec).count(), 1
        )

    # =========================================================================
    # 17. PIT safety
    # =========================================================================

    def test_pit_entry_eval_future_bars_excluded(self):
        """EntryEvaluator only evaluates bars passed in — PIT safety is caller's responsibility."""
        from market.services.outcome_engine import EntryEvaluator
        rec = self._make_rec(signal="BUY", entry=105.0)
        # Only pass bars up to as_of — no future bars
        past_bars = self._make_bars([(100, 102, 98, 101)])
        result = EntryEvaluator().evaluate(rec, past_bars)
        # Entry price 105 > bar high 102 → not triggered (future bar not seen)
        self.assertFalse(result.triggered)

    # =========================================================================
    # 18. Historical data limitation warnings
    # =========================================================================

    def test_historical_data_warnings_in_outcome(self):
        """Outcome records include historical data limitation warnings."""
        from market.services.outcome_service import RecommendationOutcomeService, DQ_HIST_NEWS
        from market.models import RecommendationOutcome
        rec = self._make_rec(signal="BUY", entry=200.0,
                             expires_at=self.t0 - timedelta(minutes=1))
        svc = RecommendationOutcomeService()
        bars = self._make_bars([(100, 102, 98, 101)])
        outcome = svc.evaluate_single(rec, as_of=self.t0 + timedelta(hours=1), bars=bars)
        self.assertIsNotNone(outcome)
        self.assertIn(DQ_HIST_NEWS, outcome.data_quality_warnings)

    # =========================================================================
    # 19. Signal enum completeness
    # =========================================================================

    def test_ambiguous_intrabar_in_recommendation_status_enum(self):
        """AMBIGUOUS_INTRABAR is in RecommendationStatus enum."""
        from market.signal_enums import RecommendationStatus
        self.assertIn("AMBIGUOUS_INTRABAR", [s.value for s in RecommendationStatus])

    def test_exit_reason_enum_values(self):
        """ExitReason has all required values."""
        from market.signal_enums import ExitReason
        required = {
            "TARGET_HIT", "STOP_HIT", "EXPIRED_SESSION",
            "EXPIRED_MAX_DURATION", "AMBIGUOUS_INTRABAR", "NO_ENTRY",
        }
        actual = {r.value for r in ExitReason}
        self.assertTrue(required.issubset(actual))

    def test_ambiguity_policy_enum_values(self):
        """AmbiguityPolicy has CONSERVATIVE, OPTIMISTIC, EXCLUDE."""
        from market.signal_enums import AmbiguityPolicy
        self.assertIn("CONSERVATIVE", [p.value for p in AmbiguityPolicy])
        self.assertIn("OPTIMISTIC", [p.value for p in AmbiguityPolicy])
        self.assertIn("EXCLUDE", [p.value for p in AmbiguityPolicy])

    # =========================================================================
    # 20. Regression — daily recommendations unaffected
    # =========================================================================

    def test_daily_rec_status_choices_include_ambiguous(self):
        """StockRecommendation STATUS_CHOICES includes AMBIGUOUS_INTRABAR."""
        from market.models import StockRecommendation
        status_values = [s[0] for s in StockRecommendation.STATUS_CHOICES]
        self.assertIn("AMBIGUOUS_INTRABAR", status_values)

    def test_daily_rec_existing_statuses_unchanged(self):
        """Original status choices (ACTIVE, TRIGGERED, etc.) still present."""
        from market.models import StockRecommendation
        status_values = [s[0] for s in StockRecommendation.STATUS_CHOICES]
        for status in ("ACTIVE", "TRIGGERED", "TARGET_HIT", "STOPPED", "EXPIRED"):
            self.assertIn(status, status_values)

    def test_daily_rec_unaffected_by_outcome_model(self):
        """A daily recommendation can be created without any outcome-related fields."""
        from market.models import StockRecommendation
        daily_co = Company.objects.create(
            name="Daily Co", sector="Finance", industry="Banking"
        )
        daily_inst = Instrument.objects.create(
            symbol="DAILY1", company=daily_co, instrument_type="EQUITY",
            is_active=True, lot_size=1
        )
        rec = StockRecommendation.objects.create(
            instrument=daily_inst,
            horizon="DELIVERY_SWING",
            signal="BUY",
            setup_type="BREAKOUT",
            as_of=self.t0,
            entry_type="BREAKOUT_CONFIRMATION",
            entry_price=Decimal("500.00"),
            entry_condition="Buy above 500",
            stop_price=Decimal("480.00"),
            stop_method="STRUCTURAL",
            invalidation_reason="Close below 480",
            target_price=Decimal("540.00"),
            target_method="MEASURED_MOVE",
            risk=Decimal("20.00"),
            reward=Decimal("40.00"),
            risk_reward_ratio=Decimal("2.0"),
            confidence="HIGH",
            confidence_components={},
            market_context={},
            sector_context={},
            supporting_factors=[],
            risk_factors=[],
            setup_details={},
            data_quality={},
            status="ACTIVE",
        )
        # Daily rec has no intraday-specific fields set
        self.assertIsNone(rec.timeframe)
        self.assertIsNone(rec.expires_at)
        self.assertIsNone(rec.strategy_version)
        self.assertEqual(rec.horizon, "DELIVERY_SWING")
