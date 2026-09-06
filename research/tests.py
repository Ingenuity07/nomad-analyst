import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from market.models import (
    Company,
    Instrument,
    MarketContextSnapshot,
    IntradayOpportunitySnapshot,
    StockIntradayContext,
    DerivedFundamentalMetric,
    IncomeStatement,
    CorporateEvent,
    NewsItem,
    TechnicalFeature
)
from research.models import ResearchRun, ResearchReport
from research.schemas import StructuredResearchOutput
from research.services.evidence_builder import ResearchEvidencePackageBuilder
from research.services.delta_service import ResearchDeltaService
from research.services.on_demand_research_service import OnDemandResearchService
from llm.contracts import LLMResult


def create_mock_llm_result(symbol: str = "TATASTEEL") -> LLMResult:
    """Helper returning a mock LLMResult with a valid StructuredResearchOutput."""
    output = StructuredResearchOutput(
        summary=f"Strong momentum continuation supported by metals sector leadership for {symbol}.",
        observed_facts=[
            f"Opportunity score is 84.0 with confidence 0.89.",
            "Trading above VWAP with positive 5m and 15m momentum.",
            "Metals sector ranked #1 in market context."
        ],
        analyst_interpretation="The confluence of sector rotation into cyclicals and strong price persistence above VWAP confirms institutional participation.",
        why_interesting=[
            "Relative strength vs NIFTY is positive.",
            "Volume confirmation confirms breakout."
        ],
        supporting_evidence=[
            "Relative volume is 2.4x average.",
            "Breadth confirms broad sector participation."
        ],
        contradicting_evidence=[
            "NIFTY overall market breadth weakened slightly in last 15 minutes."
        ],
        key_risks=[
            "Sharp reversal if index breaks below opening range low."
        ],
        unknowns=[
            "Real-time institutional block deal flow is unavailable."
        ],
        market_context_interpretation="Market is TRENDING_UP; sector tailwind supports continuation.",
        sector_context_interpretation="Metals leading all 12 tracked sectors today.",
        thesis="Constructive intraday momentum setup supported by strong sector beta.",
        thesis_strength="HIGH",
        what_to_monitor=[
            "Holding above intraday VWAP ₹155.20.",
            "Volume expansion on 15m candle close."
        ],
        invalidating_developments=[
            "Sustained 5m close below VWAP.",
            "Reversal in NIFTY METAL index."
        ],
        research_confidence="HIGH"
    )
    return LLMResult(
        output=output,
        raw_text=json.dumps(output.model_dump()),
        model="gemini-2.5-flash",
        provider="google",
        attempts=1,
        status="success",
        usage={"prompt_tokens": 850, "completion_tokens": 320, "total_tokens": 1170},
        latency_ms=1200.0
    )


class Phase17EOnDemandResearchTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.now = timezone.now()

        # Setup Company and Instrument
        self.company = Company.objects.create(
            name="Tata Steel Limited",
            short_name="TATASTEEL",
            sector="Metals",
            industry="Steel"
        )
        self.instrument = Instrument.objects.create(
            company=self.company,
            symbol="TATASTEEL",
            exchange="NSE",
            instrument_type="EQUITY",
            lot_size=1,
            is_active=True
        )

        # Setup Market Context Snapshot
        self.market_snapshot = MarketContextSnapshot.objects.create(
            as_of=self.now,
            universe="NIFTY50",
            market_regime="TRENDING_UP",
            market_direction="BULLISH",
            market_volatility="NORMAL",
            breadth_state="EXPANDING",
            index_regimes={
                "NIFTY": {"return_pct": 0.85},
                "BANKNIFTY": {"return_pct": 1.10}
            },
            breadth={
                "advances": 38,
                "declines": 12,
                "advance_decline_ratio": 3.16,
                "pct_above_vwap": 76.0
            },
            sector_rankings=[
                {"sector": "Metals", "rank": 1, "return_pct": 2.4, "momentum_state": "STRONG"},
                {"sector": "IT", "rank": 2, "return_pct": 1.2, "momentum_state": "IMPROVING"},
            ]
        )

        # Setup Stock Intraday Context
        self.intraday_ctx = StockIntradayContext.objects.create(
            instrument=self.instrument,
            timestamp=self.now,
            last_price=Decimal('156.40'),
            change_pct=Decimal('2.80'),
            vwap=Decimal('154.20'),
            distance_from_vwap=Decimal('1.43'),
            volume=4500000,
            relative_volume=Decimal('2.40'),
            momentum_5m=Decimal('0.45'),
            momentum_15m=Decimal('1.20'),
            momentum_30m=Decimal('2.10'),
            relative_strength_vs_market=Decimal('1.95'),
            relative_strength_vs_sector=Decimal('0.40'),
            sector="Metals",
            sector_return=Decimal('2.40'),
            volume_confirmation="STRONG",
            opening_range_state="ABOVE_ORB_HIGH",
            intraday_high=Decimal('157.00'),
            intraday_low=Decimal('152.50')
        )

        # Setup Intraday Opportunity Snapshot
        self.opp_snapshot = IntradayOpportunitySnapshot.objects.create(
            instrument=self.instrument,
            symbol="TATASTEEL",
            timestamp=self.now,
            opportunity_type="RELATIVE_STRENGTH",
            state="CONFIRMED",
            score=Decimal('84.00'),
            confidence=Decimal('0.89'),
            momentum_score=Decimal('85.00'),
            relative_strength_score=Decimal('90.00'),
            volume_score=Decimal('82.00'),
            vwap_score=Decimal('88.00'),
            market_alignment_score=Decimal('80.00'),
            sector_alignment_score=Decimal('95.00'),
            orb_score=Decimal('85.00'),
            data_quality_score=Decimal('90.00'),
            supporting_factors=["Strong relative strength vs NIFTY (+1.95%)", "Above VWAP"],
            contradicting_factors=["Market breadth declined slightly from peak"],
            warnings=["Watch for resistance near 158.00"],
            metrics={
                "last_price": 156.4,
                "change_pct": 2.8,
                "vwap": 154.2,
                "vwap_diff_pct": 1.43,
                "relative_volume": 2.4,
                "momentum_5m": 0.45,
                "momentum_15m": 1.20,
                "relative_strength_vs_market": 1.95
            },
            rank=1,
            sector="Metals",
            market_alignment="ALIGNED_BULLISH",
            sector_alignment="ALIGNED_BULLISH"
        )

        # Fundamentals
        IncomeStatement.objects.create(
            company=self.company,
            fiscal_year=2025,
            period_type='ANNUAL',
            period_string='Mar 2025',
            revenue=Decimal('230000.00'),
            ebitda=Decimal('24000.00'),
            pbt=Decimal('12000.00')
        )
        DerivedFundamentalMetric.objects.create(
            company=self.company,
            period_type='ANNUAL',
            period_string='FY2025',
            name='ROE',
            value=Decimal('14.50')
        )
        NewsItem.objects.create(
            company=self.company,
            headline="Tata Steel expands Kalinganagar blast furnace capacity",
            source="Moneycontrol",
            content_hash="tatasteel_news_hash_001",
            published_at=self.now - timedelta(hours=2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ONE-CALL GUARANTEE & COST CONTROL TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_examine_new_triggers_exactly_one_llm_call(self):
        """User requests new research -> exactly 1 provider call made."""
        mock_router = MagicMock()
        mock_router.execute.return_value = create_mock_llm_result("TATASTEEL")

        svc = OnDemandResearchService(provider=mock_router)
        res = svc.examine(symbol="TATASTEEL", mode="INTRADAY")

        self.assertEqual(mock_router.execute.call_count, 1)
        self.assertFalse(res["reused"])
        self.assertEqual(res["llm_calls_made"], 1)
        self.assertEqual(res["research_run"].status, "completed")
        self.assertEqual(res["research_run"].symbol, "TATASTEEL")
        self.assertIn("metals sector leadership", res["research_run"].research_output["summary"].lower())

    def test_open_existing_research_triggers_zero_llm_calls(self):
        """User opens existing cached research -> ZERO LLM calls."""
        mock_router = MagicMock()
        mock_router.execute.return_value = create_mock_llm_result("TATASTEEL")

        svc = OnDemandResearchService(provider=mock_router)

        # 1st call: new examine -> 1 call
        res1 = svc.examine(symbol="TATASTEEL", mode="INTRADAY")
        self.assertEqual(mock_router.execute.call_count, 1)
        self.assertFalse(res1["reused"])

        # 2nd call: reopen same stock & mode -> 0 calls
        res2 = svc.examine(symbol="TATASTEEL", mode="INTRADAY")
        self.assertEqual(mock_router.execute.call_count, 1) # Still 1!
        self.assertTrue(res2["reused"])
        self.assertEqual(res2["llm_calls_made"], 0)
        self.assertEqual(res2["research_run"].id, res1["research_run"].id)

    def test_explicit_refresh_triggers_one_llm_call(self):
        """User explicitly clicks refresh -> exactly 1 new LLM call."""
        mock_router = MagicMock()
        mock_router.execute.return_value = create_mock_llm_result("TATASTEEL")

        svc = OnDemandResearchService(provider=mock_router)

        # Initial research
        res1 = svc.examine(symbol="TATASTEEL", mode="INTRADAY")
        self.assertEqual(mock_router.execute.call_count, 1)

        # Explicit refresh
        res_refresh = svc.refresh(research_run_id=str(res1["research_run"].id))
        self.assertEqual(mock_router.execute.call_count, 2)
        self.assertFalse(res_refresh["reused"])
        self.assertEqual(res_refresh["llm_calls_made"], 1)
        self.assertEqual(res_refresh["research_run"].status, "completed")

    def test_market_update_triggers_zero_llm_calls(self):
        """Market context updates deterministically -> ZERO LLM calls."""
        mock_router = MagicMock()
        mock_router.execute.return_value = create_mock_llm_result("TATASTEEL")

        svc = OnDemandResearchService(provider=mock_router)
        res = svc.examine(symbol="TATASTEEL", mode="INTRADAY")
        self.assertEqual(mock_router.execute.call_count, 1)

        # Simulate new MarketContextSnapshot created by intraday pipeline
        MarketContextSnapshot.objects.create(
            as_of=self.now + timedelta(minutes=5),
            universe="NIFTY50",
            market_regime="TRANSITIONING",
            market_direction="NEUTRAL",
            breadth={"advances": 25, "declines": 25}
        )

        # Reopen research / delta
        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(res["research_run"])

        self.assertEqual(mock_router.execute.call_count, 1) # Still 1!
        self.assertTrue(delta["zero_llm_call_verified"])
        self.assertTrue(delta["deltas"]["regime_changed"])

    def test_opportunity_rank_change_triggers_zero_llm_calls(self):
        """Opportunity score/rank changes deterministically -> ZERO LLM calls."""
        mock_router = MagicMock()
        mock_router.execute.return_value = create_mock_llm_result("TATASTEEL")

        svc = OnDemandResearchService(provider=mock_router)
        res = svc.examine(symbol="TATASTEEL", mode="INTRADAY")
        self.assertEqual(mock_router.execute.call_count, 1)

        # Update opportunity snapshot to new score & rank
        self.opp_snapshot.score = Decimal('78.00')
        self.opp_snapshot.rank = 3
        self.opp_snapshot.state = "WEAKENING"
        self.opp_snapshot.save()

        # Delta evaluation
        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(res["research_run"])

        self.assertEqual(mock_router.execute.call_count, 1) # ZERO LLM calls
        self.assertEqual(delta["deltas"]["score_change"], -6.0)
        self.assertEqual(delta["deltas"]["rank_change"], 2)
        self.assertTrue(delta["deltas"]["state_changed"])

    # ─────────────────────────────────────────────────────────────────────────
    # 2. EVIDENCE PACKAGE BUILDER TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_evidence_builder_intraday(self):
        builder = ResearchEvidencePackageBuilder()
        pkg = builder.build_package(symbol="TATASTEEL", mode="INTRADAY")

        self.assertEqual(pkg["research_mode"], "INTRADAY")
        self.assertEqual(pkg["asset"], "TATASTEEL")
        self.assertEqual(pkg["opportunity"]["score"], 84.0)
        self.assertEqual(pkg["opportunity"]["opportunity_type"], "RELATIVE_STRENGTH")
        self.assertEqual(pkg["market_context"]["regime"], "TRENDING_UP")
        self.assertEqual(pkg["sector_context"]["sector"], "Metals")
        self.assertEqual(pkg["sector_context"]["rank"], 1)
        self.assertIn("evidence_hash", pkg)
        self.assertTrue(len(pkg["evidence_hash"]) == 64)

        # Check deterministic summary
        summary = pkg["deterministic_summary"]
        self.assertEqual(summary["opportunity_score"], 84.0)
        self.assertEqual(summary["opportunity_rank"], 1)
        self.assertTrue(summary["generated_deterministically"])

    def test_evidence_builder_long_term_audit_notes(self):
        builder = ResearchEvidencePackageBuilder()
        pkg = builder.build_package(symbol="TATASTEEL", mode="LONG_TERM")

        self.assertEqual(pkg["research_mode"], "LONG_TERM")
        self.assertIn("derived_metrics", pkg["fundamentals"])
        self.assertIn("annual_statements", pkg["fundamentals"])
        self.assertIn("horizon_v1_audit_notes", pkg["opportunity"])

    def test_evidence_builder_missing_data_transparency(self):
        """Missing company or indicators are reported explicitly, never converted to 0."""
        builder = ResearchEvidencePackageBuilder()
        pkg = builder.build_package(symbol="NONEXISTENT_SYM", mode="INTRADAY")

        self.assertEqual(pkg["company"]["status"], "UNAVAILABLE")
        self.assertEqual(pkg["opportunity"]["status"], "UNAVAILABLE")
        self.assertIn("company_profile", pkg["data_quality"]["missing_data"])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. RESEARCH DELTA SERVICE TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_research_delta_service(self):
        # Create a mock completed run
        run = ResearchRun.objects.create(
            symbol="TATASTEEL",
            research_mode="INTRADAY",
            status="completed",
            opportunity_score_at_research=84.0,
            opportunity_state_at_research="CONFIRMED",
            evidence_snapshot={
                "opportunity": {"score": 84.0, "rank": 1, "state": "CONFIRMED"},
                "market_context": {"regime": "TRENDING_UP"},
                "sector_context": {"sector": "Metals", "rank": 1},
                "stock_context": {"momentum_5m": 0.45, "distance_from_vwap": 1.43}
            }
        )

        delta_svc = ResearchDeltaService()
        delta = delta_svc.compute_delta(run)

        self.assertEqual(delta["symbol"], "TATASTEEL")
        self.assertEqual(delta["basis"]["score"], 84.0)
        self.assertEqual(delta["basis"]["rank"], 1)
        self.assertEqual(delta["deltas"]["score_change"], 0.0)
        self.assertFalse(delta["deltas"]["state_changed"])
        self.assertTrue(delta["zero_llm_call_verified"])

    # ─────────────────────────────────────────────────────────────────────────
    # 4. FAILURE & TIMEOUT HANDLING
    # ─────────────────────────────────────────────────────────────────────────

    def test_provider_error_marks_failed(self):
        mock_router = MagicMock()
        mock_router.execute.return_value = LLMResult(
            output=None,
            raw_text="Rate limit exceeded",
            model="gemini-2.5-flash",
            provider="google",
            status="error",
            error_category="RATE_LIMITED",
            error_message="Provider 429 quota exhausted"
        )

        svc = OnDemandResearchService(provider=mock_router)
        res = svc.examine(symbol="TATASTEEL", mode="INTRADAY")

        self.assertEqual(res["research_run"].status, "failed")
        self.assertIn("quota exhausted", res["research_run"].error_message)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. REST API ENDPOINT TESTS
    # ─────────────────────────────────────────────────────────────────────────

    @patch('research.services.on_demand_research_service.llm_service')
    def test_api_examine_endpoint(self, mock_llm):
        mock_llm.execute.return_value = create_mock_llm_result("TATASTEEL")

        url = reverse('api-research-examine')
        resp = self.client.post(url, {"symbol": "TATASTEEL", "mode": "INTRADAY"}, format='json')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('research', data)
        self.assertIn('delta', data)
        self.assertFalse(data['reused'])
        self.assertEqual(data['llm_calls_made'], 1)
        self.assertEqual(data['research']['symbol'], 'TATASTEEL')

    @patch('research.services.on_demand_research_service.llm_service')
    def test_api_get_detail_endpoint(self, mock_llm):
        run = ResearchRun.objects.create(
            symbol="TATASTEEL",
            research_mode="INTRADAY",
            status="completed",
            opportunity_score_at_research=84.0,
            research_output={"summary": "Detailed research report", "thesis": "Bullish continuation"},
            evidence_snapshot={"opportunity": {"score": 84.0, "rank": 1}}
        )

        url = reverse('api-research-detail', kwargs={'id': str(run.id)})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['research']['id'], str(run.id))
        self.assertTrue(data['zero_llm_call_verified'])
        self.assertEqual(mock_llm.execute.call_count, 0) # 0 calls

    @patch('research.services.on_demand_research_service.llm_service')
    def test_api_get_company_research_endpoint(self, mock_llm):
        ResearchRun.objects.create(
            symbol="TATASTEEL",
            research_mode="INTRADAY",
            status="completed",
            opportunity_score_at_research=84.0,
            research_output={"summary": "Company research"},
            evidence_snapshot={"opportunity": {"score": 84.0}}
        )

        url = reverse('api-research-company', kwargs={'symbol': 'TATASTEEL'})
        resp = self.client.get(url, {'mode': 'INTRADAY'})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['exists'])
        self.assertEqual(data['research']['symbol'], 'TATASTEEL')
        self.assertEqual(mock_llm.execute.call_count, 0)

    @patch('research.services.on_demand_research_service.llm_service')
    def test_api_refresh_endpoint(self, mock_llm):
        mock_llm.execute.return_value = create_mock_llm_result("TATASTEEL")

        run = ResearchRun.objects.create(
            symbol="TATASTEEL",
            research_mode="INTRADAY",
            status="completed",
            opportunity_score_at_research=84.0,
            research_output={"summary": "Initial report"}
        )

        url = reverse('api-research-refresh', kwargs={'id': str(run.id)})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['refreshed'])
        self.assertEqual(data['llm_calls_made'], 1)

    @patch('research.services.on_demand_research_service.llm_service')
    def test_api_delta_endpoint(self, mock_llm):
        run = ResearchRun.objects.create(
            symbol="TATASTEEL",
            research_mode="INTRADAY",
            status="completed",
            opportunity_score_at_research=84.0,
            evidence_snapshot={"opportunity": {"score": 84.0, "rank": 1}}
        )

        url = reverse('api-research-delta', kwargs={'id': str(run.id)})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['zero_llm_call_verified'])
        self.assertEqual(mock_llm.execute.call_count, 0)
