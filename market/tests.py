from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import numpy as np
import requests

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
    CorporateDisclosure
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


