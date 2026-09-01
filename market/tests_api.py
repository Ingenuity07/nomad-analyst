import uuid
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status

from market.models import (
    Company, Instrument, MarketSnapshot, OHLCVBar, TechnicalFeature,
    IncomeStatement, BalanceSheetStatement, CashFlowStatement, DerivedFundamentalMetric,
    NewsItem, CorporateDisclosure, MarketContextSnapshot,
    StockOpportunitySnapshot, StockRecommendation, RecommendationOutcome, BacktestRun
)


class RestApiV1TestCase(APITestCase):
    """
    Comprehensive test suite for Nomad Analyst v1 REST API endpoints.
    Tests every endpoint for success, validation, filtering, pagination,
    data-quality states, and error handling.
    """

    def setUp(self):
        self.company = Company.objects.create(
            name="Reliance Industries Limited",
            short_name="RELIANCE",
            sector="Energy",
            industry="Oil & Gas"
        )
        self.instrument = Instrument.objects.create(
            company=self.company,
            symbol="RELIANCE",
            exchange="NSE",
            instrument_type="EQUITY"
        )
        self.snapshot = MarketSnapshot.objects.create(
            instrument=self.instrument,
            timestamp=timezone.now(),
            open=Decimal("1280.00"),
            high=Decimal("1311.80"),
            low=Decimal("1280.00"),
            close=Decimal("1309.00"),
            volume=12613543,
            previous_close=Decimal("1277.00"),
            change=Decimal("32.00"),
            change_percent=Decimal("2.51"),
            source="yfinance"
        )
        self.bar = OHLCVBar.objects.create(
            instrument=self.instrument,
            timeframe="1d",
            timestamp=timezone.now() - timedelta(days=1),
            open=Decimal("1280.00"),
            high=Decimal("1295.00"),
            low=Decimal("1275.00"),
            close=Decimal("1290.00"),
            volume=8500000,
            source="yfinance"
        )
        self.feature = TechnicalFeature.objects.create(
            instrument=self.instrument,
            timeframe="1d",
            timestamp=self.bar.timestamp,
            name="SMA",
            parameters={"period": 50},
            param_key="period=50",
            value=Decimal("1260.500000")
        )
        self.income_stmt = IncomeStatement.objects.create(
            company=self.company,
            fiscal_year=2026,
            period_type="ANNUAL",
            period_string="Mar 2026",
            revenue=Decimal("1055780.00"),
            expenses=Decimal("876715.00"),
            ebitda=Decimal("179065.00"),
            ebit=Decimal("124965.00"),
            pbt=Decimal("100165.00"),
            pat=Decimal("95754.00"),
            eps=Decimal("59.69")
        )
        self.metric = DerivedFundamentalMetric.objects.create(
            company=self.company,
            period_type="ANNUAL",
            period_string="Mar 2026",
            name="return_on_equity",
            value=Decimal("18.2000")
        )
        self.news = NewsItem.objects.create(
            company=self.company,
            instrument=self.instrument,
            headline="Reliance reports strong quarterly earnings growth",
            summary="Revenue up 8.2% YoY driven by retail and oil-to-chemicals.",
            source="Reuters",
            source_id="news_123",
            url="https://reuters.com/article/123",
            published_at=timezone.now() - timedelta(hours=2),
            content_hash="hash_reliance_123"
        )
        self.disclosure = CorporateDisclosure.objects.create(
            company=self.company,
            headline="Board Meeting Outcome - Financial Results",
            category="Financial Results",
            source="NSE",
            announcement_id="ann_987",
            url="https://nseindia.com/ann/987",
            published_at=timezone.now() - timedelta(hours=3),
            details={"type": "earnings"}
        )
        self.opp_snapshot = StockOpportunitySnapshot.objects.create(
            instrument=self.instrument,
            as_of=timezone.now(),
            universe="NIFTY50",
            horizon="DELIVERY_SWING",
            opportunity_type="MOMENTUM_BREAKOUT",
            component_scores={"technical": 97.0, "fundamental": 56.0, "sector": 100.0},
            final_opportunity_score=Decimal("87.0000"),
            supporting_features={"pros": ["Trading above 50-day SMA"]},
            risks=["Resistance at ₹1,325.0"],
            data_quality={"status": "COMPLETE"}
        )
        self.recommendation = StockRecommendation.objects.create(
            instrument=self.instrument,
            as_of=timezone.now(),
            horizon="DELIVERY_SWING",
            signal="BUY",
            setup_type="MOMENTUM_BREAKOUT",
            timeframe="1d",
            confidence="HIGH",
            status="ACTIVE",
            entry_type="BREAKOUT_CONFIRMATION",
            entry_price=Decimal("1309.00"),
            entry_condition="Close above 1300",
            stop_price=Decimal("1280.00"),
            stop_method="STRUCTURAL",
            invalidation_reason="Close below 1280",
            target_price=Decimal("1360.00"),
            target_method="RESISTANCE_LEVEL",
            target_2_price=Decimal("1410.00"),
            target_2_method="MEASURED_MOVE",
            risk=Decimal("29.00"),
            reward=Decimal("51.00"),
            risk_reward_ratio=Decimal("1.7586"),
            supporting_factors=["Strong volume expansion"],
            risk_factors=["Overhead resistance"]
        )
        self.outcome = RecommendationOutcome.objects.create(
            recommendation=self.recommendation,
            evaluation_version=1,
            evaluated_at=timezone.now(),
            entry_triggered=True,
            entry_timestamp=timezone.now() - timedelta(hours=1),
            actual_entry_price=Decimal("1309.00"),
            exit_reason="TARGET_HIT",
            exit_timestamp=timezone.now(),
            actual_exit_price=Decimal("1360.00"),
            net_pnl_percent=Decimal("3.8961"),
            r_multiple=Decimal("1.7586"),
            bars_evaluated=5
        )
        self.backtest = BacktestRun.objects.create(
            run_id="NIFTY50_1d_DELIVERY_SWING_2026-03-01_2026-09-01_test",
            config={"universe": "NIFTY50", "timeframe": "1d"},
            status="COMPLETE",
            universe_name="NIFTY50",
            timeframe="1d",
            horizon="DELIVERY_SWING",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 9, 1),
            strategy_version="1.0.0",
            result={"total_signals": 10, "win_rate": 0.70, "avg_r": 1.5}
        )

    # ── 1. Market APIs ────────────────────────────────────────────────────────
    def test_market_overview_endpoint(self):
        url = "/api/v1/market/overview/?universe=NIFTY50"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("as_of", data)
        self.assertIn("universe", data)
        self.assertIn("market_session", data)
        self.assertIn("breadth", data)
        self.assertIn("index_regimes", data)
        self.assertIn("data_freshness", data)

    def test_market_indices_endpoint(self):
        url = "/api/v1/market/indices/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("indices", data)

    def test_market_regime_endpoint(self):
        url = "/api/v1/market/regime/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("index_regimes", data)
        self.assertIn("breadth_regime", data)

    def test_market_breadth_endpoint(self):
        url = "/api/v1/market/breadth/?universe=NIFTY50"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["universe"], "NIFTY50")
        self.assertIn("breadth", data)

    def test_market_sectors_endpoint(self):
        url = "/api/v1/market/sectors/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("sector_rankings", data)

    def test_market_global_cues_endpoint(self):
        url = "/api/v1/market/global/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("global_cues", data)

    # ── 2. Stock APIs ─────────────────────────────────────────────────────────
    def test_stock_list_and_search(self):
        # List
        url = "/api/v1/stocks/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertGreaterEqual(data["count"], 1)

        # Search
        search_url = "/api/v1/stocks/search/?q=reli"
        search_resp = self.client.get(search_url)
        self.assertEqual(search_resp.status_code, status.HTTP_200_OK)
        search_data = search_resp.json()
        self.assertIn("results", search_data)
        self.assertTrue(any(r["symbol"] == "RELIANCE" for r in search_data["results"]))

    def test_stock_detail_and_not_found(self):
        # Found
        url = "/api/v1/stocks/RELIANCE/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["instrument"]["symbol"], "RELIANCE")
        self.assertIsNotNone(data["latest_snapshot"])
        self.assertEqual(float(data["latest_snapshot"]["close"]), 1309.0)

        # Not found
        nf_url = "/api/v1/stocks/UNKNOWN_SYM/"
        nf_resp = self.client.get(nf_url)
        self.assertEqual(nf_resp.status_code, status.HTTP_404_NOT_FOUND)
        nf_data = nf_resp.json()
        self.assertIn("error", nf_data)
        self.assertEqual(nf_data["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_stock_ohlcv(self):
        url = "/api/v1/stocks/RELIANCE/ohlcv/?timeframe=1d&limit=10"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["symbol"], "RELIANCE")
        self.assertEqual(data["timeframe"], "1d")
        self.assertGreaterEqual(data["bars_count"], 1)

    def test_stock_technicals(self):
        url = "/api/v1/stocks/RELIANCE/technicals/?timeframe=1d"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["symbol"], "RELIANCE")
        self.assertIn("SMA", data["indicators"])
        self.assertEqual(data["indicators"]["SMA"]["value"], 1260.5)

    def test_stock_fundamentals(self):
        url = "/api/v1/stocks/RELIANCE/fundamentals/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["symbol"], "RELIANCE")
        self.assertIn("income_statement", data["statements"])
        self.assertIn("metrics", data)

    def test_stock_news_and_events(self):
        # News
        news_url = "/api/v1/stocks/RELIANCE/news/"
        news_resp = self.client.get(news_url)
        self.assertEqual(news_resp.status_code, status.HTTP_200_OK)
        news_data = news_resp.json()
        self.assertGreaterEqual(news_data["count"], 1)

        # Events
        events_url = "/api/v1/stocks/RELIANCE/events/"
        events_resp = self.client.get(events_url)
        self.assertEqual(events_resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(events_resp.json()["count"], 1)

    # ── 3. Opportunities & Recommendations ───────────────────────────────────
    def test_opportunities_list_and_detail(self):
        # List
        url = "/api/v1/opportunities/?universe=NIFTY50&horizon=DELIVERY_SWING"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)

        # Detail
        opp_id = self.opp_snapshot.id
        detail_url = f"/api/v1/opportunities/{opp_id}/"
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["symbol"], "RELIANCE")
        self.assertEqual(float(detail_data["final_opportunity_score"]), 87.0)

    def test_recommendations_list_and_detail(self):
        # List
        url = "/api/v1/recommendations/?horizon=DELIVERY_SWING&status=ACTIVE"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)

        # Detail
        rec_id = self.recommendation.id
        detail_url = f"/api/v1/recommendations/{rec_id}/"
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["symbol"], "RELIANCE")
        self.assertEqual(float(detail_data["entry_price"]), 1309.0)

    # ── 4. Intraday Intelligence ──────────────────────────────────────────────
    def test_intraday_endpoints(self):
        # Overview
        url = "/api/v1/intraday/overview/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("market_session", data)
        self.assertIn("summary", data)

        # Recommendations
        rec_url = "/api/v1/intraday/recommendations/"
        rec_resp = self.client.get(rec_url)
        self.assertEqual(rec_resp.status_code, status.HTTP_200_OK)

        # Data Quality
        dq_url = "/api/v1/intraday/data-quality/?symbol=RELIANCE&timeframe=5m"
        dq_resp = self.client.get(dq_url)
        self.assertEqual(dq_resp.status_code, status.HTTP_200_OK)
        dq_data = dq_resp.json()
        self.assertEqual(dq_data["symbol"], "RELIANCE")
        self.assertIn("is_ready", dq_data)

    # ── 5. Outcomes & Strategy Performance ────────────────────────────────────
    def test_outcome_and_strategy_performance(self):
        # Recommendation Outcome
        rec_id = self.recommendation.id
        url = f"/api/v1/recommendations/{rec_id}/outcome/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["symbol"], "RELIANCE")
        self.assertEqual(data["exit_reason"], "TARGET_HIT")
        self.assertEqual(float(data["r_multiple"]), 1.7586)

        # Outcomes List
        list_url = "/api/v1/outcomes/"
        list_resp = self.client.get(list_url)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_resp.json()["count"], 1)

        # Strategies List
        strat_url = "/api/v1/strategies/"
        strat_resp = self.client.get(strat_url)
        self.assertEqual(strat_resp.status_code, status.HTTP_200_OK)
        self.assertIn("strategies", strat_resp.json())

        # Strategy Performance
        perf_url = "/api/v1/strategies/DELIVERY_SWING/performance/"
        perf_resp = self.client.get(perf_url)
        self.assertEqual(perf_resp.status_code, status.HTTP_200_OK)
        perf_data = perf_resp.json()
        self.assertEqual(perf_data["strategy"], "DELIVERY_SWING")
        self.assertEqual(perf_data["wins"], 1)

    # ── 6. Backtest APIs ──────────────────────────────────────────────────────
    def test_backtest_list_detail_and_run(self):
        # List
        url = "/api/v1/backtests/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreaterEqual(data["count"], 1)

        # Detail
        detail_url = f"/api/v1/backtests/{self.backtest.run_id}/"
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        detail_data = detail_resp.json()
        self.assertEqual(detail_data["run_id"], self.backtest.run_id)
        self.assertEqual(detail_data["status"], "COMPLETE")

        # Run
        run_payload = {
            "universe_name": "NIFTY50",
            "timeframe": "1d",
            "horizon": "DELIVERY_SWING",
            "start_date": "2026-03-01",
            "end_date": "2026-09-01",
            "cost_mode": "REALISTIC",
            "ambiguity_policy": "CONSERVATIVE"
        }
        run_url = "/api/v1/backtests/run/"
        run_resp = self.client.post(run_url, data=run_payload, format="json")
        self.assertEqual(run_resp.status_code, status.HTTP_201_CREATED)
        run_data = run_resp.json()
        self.assertIn("run_id", run_data)
        self.assertEqual(run_data["status"], "COMPLETE")

    # ── 7. AI Stock Research API ──────────────────────────────────────────────
    @patch("market.services.market_research_service.MarketResearchService.research_stock")
    def test_ai_research_endpoint(self, mock_research):
        mock_research.return_value = {
            "company": "Reliance Industries Limited",
            "instrument": "RELIANCE",
            "as_of": None,
            "summary": "Mock research report summary on RELIANCE.",
            "market_snapshot": {"price": 1309.0},
            "technical_analysis": "Bullish trend above 200 SMA",
            "fundamental_analysis": "Consistent PAT growth",
            "news_analysis": "No negative news",
            "positive_factors": ["High ROE"],
            "risks": ["Resistance at 1325"],
            "contradictions": [],
            "unknowns": [],
            "evidence": ["NSE Snapshot"],
            "generated_at": timezone.now().isoformat()
        }

        url = "/api/v1/research/"
        payload = {
            "symbol": "RELIANCE",
            "question": "Provide complete equity analysis.",
            "depth": "standard"
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["instrument"], "RELIANCE")
        self.assertIn("summary", data)
        self.assertIn("positive_factors", data)
