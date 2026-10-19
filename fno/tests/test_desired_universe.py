"""
Unit Tests for AC-1-U03: DesiredUniverseManager.
Verifies ATM strike calculation, dynamic spot shift rebalancing, and expiry staging policies.
"""

import tempfile
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from fno.services.desired_universe import DesiredUniverseManager
from fno.services.option_registry import (
    OptionContractMeta,
    OptionInstrumentRegistry,
    UnderlyingAssetConfig,
)

CSV_HEADER = "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,tick_size,lot_size,instrument_type,segment,exchange\n"


def generate_universe_csv() -> str:
    """Generates synthetic CSV rows covering strikes 24000 to 25000 for two expiries."""
    rows = []
    token = 1000000
    for exp_str in ("2026-10-15", "2026-10-22"):
        for strike in range(24000, 25050, 50):
            for opt_type in ("CE", "PE"):
                sym = f"NIFTY26O{strike}{opt_type}_{exp_str}"
                rows.append(
                    f"{token},{token},{sym},\"NIFTY\",0,{exp_str},{strike},0.05,25,{opt_type},NFO-OPT,NFO\n"
                )
                token += 1
    return CSV_HEADER + "".join(rows)


class TestDesiredUniverseManager(SimpleTestCase):
    """Test suite for DesiredUniverseManager meeting AC-1-U03."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_file = Path(self.temp_dir.name) / "instruments.csv"
        self.csv_file.write_text(generate_universe_csv(), encoding="utf-8")

        self.registry = OptionInstrumentRegistry(master_path=self.csv_file)
        self.registry.load_master()

        self.config = UnderlyingAssetConfig(
            underlying_symbol="^NSEI",
            underlying_name="NIFTY 50",
            master_name="NIFTY",
            strike_step=Decimal("50.0"),
            strike_window_k=5,
            rebalance_threshold_pts=Decimal("50.0"),
            next_weekly_staging_policy_time=time(13, 0),
        )
        self.manager = DesiredUniverseManager(self.registry, self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_calculate_atm_strike(self):
        """Mathematical ATM strike resolution must round to nearest strike step."""
        # Step is 50.0
        self.assertEqual(self.manager.calculate_atm_strike(Decimal("24524.49")), Decimal("24500.0"))
        self.assertEqual(self.manager.calculate_atm_strike(Decimal("24525.00")), Decimal("24550.0"))
        self.assertEqual(self.manager.calculate_atm_strike(Decimal("24549.99")), Decimal("24550.0"))
        self.assertEqual(self.manager.calculate_atm_strike(Decimal("24550.00")), Decimal("24550.0"))

    def test_calculate_desired_universe_at_initial_spot(self):
        """Initial spot at 24500 with K=5 must resolve exactly 22 contracts (11 CE + 11 PE)."""
        spot = Decimal("24500.00")
        as_of = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        desired_tokens = self.manager.calculate_desired_tokens(spot, as_of)

        # 11 strikes: 24250, 24300, 24350, 24400, 24450, 24500, 24550, 24600, 24650, 24700, 24750
        # 11 CE + 11 PE = 22 contracts
        self.assertEqual(len(desired_tokens), 22)

        # Initial reconciliation must subscribe all 22 tokens
        to_sub, to_unsub = self.manager.reconcile(spot, as_of)
        self.assertEqual(len(to_sub), 22)
        self.assertEqual(len(to_unsub), 0)

        # Commit initial reconciliation
        self.manager.apply_reconciliation(to_sub, to_unsub, spot, as_of)
        self.assertEqual(len(self.manager.active_tokens), 22)

    def test_rebalance_suppression_on_small_spot_drift(self):
        """Small spot movements below rebalance_threshold_pts must NOT trigger rebalance."""
        initial_spot = Decimal("24500.00")
        as_of = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        to_sub, to_unsub = self.manager.reconcile(initial_spot, as_of)
        self.manager.apply_reconciliation(to_sub, to_unsub, initial_spot, as_of)

        # Spot drifts by +20 points (below 50 pt threshold)
        drift_spot = Decimal("24520.00")
        to_sub, to_unsub = self.manager.reconcile(drift_spot, as_of)
        self.assertEqual(len(to_sub), 0)
        self.assertEqual(len(to_unsub), 0)

    def test_rebalance_trigger_on_significant_spot_movement(self):
        """Spot movement >= 50 points must rebalance: subscribe higher strikes, unsubscribe lower."""
        initial_spot = Decimal("24500.00")
        as_of = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        to_sub, to_unsub = self.manager.reconcile(initial_spot, as_of)
        self.manager.apply_reconciliation(to_sub, to_unsub, initial_spot, as_of)

        # Spot moves up 100 points to 24600 (ATM shifts from 24500 to 24600: +2 strikes)
        new_spot = Decimal("24600.00")
        to_sub, to_unsub = self.manager.reconcile(new_spot, as_of)

        # 2 new strikes added (24800, 24850) * 2 = 4 contracts to subscribe
        # 2 old strikes removed (24250, 24300) * 2 = 4 contracts to unsubscribe
        self.assertEqual(len(to_sub), 4)
        self.assertEqual(len(to_unsub), 4)

        # Apply and check active tokens count remains 22
        self.manager.apply_reconciliation(to_sub, to_unsub, new_spot, as_of)
        self.assertEqual(len(self.manager.active_tokens), 22)

    def test_next_weekly_staging_policy_on_expiry_day(self):
        """On expiry day after 13:00 IST, Next-Weekly contracts (K=3, 14 contracts) must be staged."""
        spot = Decimal("24500.00")
        # Expiry day 2026-10-15 at 12:30 IST (before 13:00 policy time)
        before_staging = datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc)
        contracts_before = self.manager.get_desired_contracts(spot, before_staging)
        self.assertEqual(len(contracts_before), 22)

        # Expiry day 2026-10-15 at 13:15 IST (after 13:00 policy time)
        after_staging = datetime(2026, 10, 15, 13, 15, tzinfo=timezone.utc)
        contracts_after = self.manager.get_desired_contracts(spot, after_staging)
        
        # 22 Primary Active (2026-10-15) + 14 Next-Weekly (2026-10-22, K=3 -> 7 strikes * 2 = 14) = 36
        self.assertEqual(len(contracts_after), 36)
        
        # Verify next weekly contracts are present
        next_exp_contracts = [c for c in contracts_after if c.expiry == date(2026, 10, 22)]
        self.assertEqual(len(next_exp_contracts), 14)

    def test_atm_boundary_crossing_rebalance_spot_24524_to_24526(self):
        """
        Regression test: Spot moves from 24,524.00 to 24,526.00 across the 50-point strike midpoint.
        Even though spot movement is only 2 points (below the 50-point drift threshold),
        ATM shifts from 24,500 to 24,550 and must trigger rebalancing immediately.
        """
        as_of = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        spot_1 = Decimal("24524.00")
        to_sub_1, to_unsub_1 = self.manager.reconcile(spot_1, as_of)
        self.manager.apply_reconciliation(to_sub_1, to_unsub_1, spot_1, as_of)

        self.assertEqual(self.manager.last_atm_strike, Decimal("24500.0"))
        self.assertEqual(len(self.manager.active_tokens), 22)

        # Spot moves by only 2 points, crossing the midpoint 24525.0
        spot_2 = Decimal("24526.00")
        self.assertEqual(self.manager.calculate_atm_strike(spot_2), Decimal("24550.0"))
        self.assertTrue(self.manager.should_rebalance(spot_2, as_of))

        to_sub_2, to_unsub_2 = self.manager.reconcile(spot_2, as_of)
        # Exactly 1 new strike (24800 CE & PE) added, 1 old strike (24250 CE & PE) dropped
        self.assertEqual(len(to_sub_2), 2)
        self.assertEqual(len(to_unsub_2), 2)

        self.manager.apply_reconciliation(to_sub_2, to_unsub_2, spot_2, as_of)
        self.assertEqual(self.manager.last_atm_strike, Decimal("24550.0"))
        self.assertEqual(len(self.manager.active_tokens), 22)

    def test_reconcile_against_active_tokens(self):
        """reconcile_against_active must reconcile desired set against external active tokens without side-effects."""
        as_of = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        spot = Decimal("24500.00")
        desired = self.manager.calculate_desired_tokens(spot, as_of)
        self.assertEqual(len(desired), 22)

        # Simulate external active set having only 20 of the tokens plus 2 stale foreign tokens
        desired_list = list(desired)
        external_active = set(desired_list[:20]) | {9999991, 9999992}

        to_sub, to_unsub = self.manager.reconcile_against_active(external_active, spot, as_of)
        self.assertEqual(len(to_sub), 2)
        self.assertEqual(to_sub, set(desired_list[20:]))
        self.assertEqual(to_unsub, {9999991, 9999992})
