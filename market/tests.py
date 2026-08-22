from django.test import TestCase
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import requests

from market.models import Company, Instrument, MarketSnapshot
from market.providers.yfinance import YFinanceMarketProvider
from market.normalizers.yfinance import YFinanceNormalizer
from market.services.market_service import MarketService
from market.exceptions import (
    ProviderConnectionError,
    RateLimitExceededError,
    SymbolNotFoundError,
    InvalidPayloadError,
    AuthenticationError
)
from llm.tools.registry import ToolRegistry
from llm.tools.executor import ToolExecutor
from llm.tools.implementations.market_tool import GetStockSnapshotTool

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
                    "regularMarketTime": 1787305502,  # Fixed timestamp
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
        
        # Adjust mock response time to current system time to pass stale checks
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
        
        # Ensure timestamp is fresh so it passes normalization gates
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

        # Initialize tool structures
        registry = ToolRegistry()
        tool = GetStockSnapshotTool()
        registry.register(tool)
        executor = ToolExecutor(registry=registry)

        # Execute tool via execution boundary
        result = executor.execute("get_stock_snapshot", {"symbol": "RELIANCE"})
        
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "YFinanceMarketProvider")
        self.assertEqual(result.data["symbol"], "RELIANCE")
        self.assertEqual(result.data["price"], 2500.0)
        self.assertEqual(result.data["volume"], 2000000)
        
        # Verify persistence is successfully completed during tool run
        self.assertEqual(MarketSnapshot.objects.filter(instrument__symbol="RELIANCE").count(), 1)
