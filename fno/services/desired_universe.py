"""
F&O Desired-Universe Reconciliation Service.
Calculates desired option token universe from spot prices, ATM strike windows, and expiry lifecycles.
Generates minimal token diffs (to_subscribe / to_unsubscribe) to maintain synchronized subscriptions.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Set, Tuple

from fno.services.option_registry import (
    CONFIG_NIFTY,
    OptionContractMeta,
    OptionInstrumentRegistry,
    UnderlyingAssetConfig,
)

logger = logging.getLogger(__name__)


class DesiredUniverseManager:
    """
    Stateful manager computing desired option universe based on underlying spot price,
    strike window, and expiry lifecycle policies.
    """

    def __init__(
        self,
        registry: OptionInstrumentRegistry,
        config: Optional[UnderlyingAssetConfig] = None
    ):
        self.registry = registry
        self.config = config or CONFIG_NIFTY
        self._active_tokens: Set[int] = set()
        self._last_rebalance_spot: Optional[Decimal] = None
        self._last_atm_strike: Optional[Decimal] = None
        self._last_rebalance_time: Optional[datetime] = None
        self._current_primary_expiry: Optional[date] = None

    @property
    def active_tokens(self) -> Set[int]:
        """Currently active/subscribed token set."""
        return set(self._active_tokens)

    @property
    def last_rebalance_spot(self) -> Optional[Decimal]:
        return self._last_rebalance_spot

    @property
    def last_atm_strike(self) -> Optional[Decimal]:
        return self._last_atm_strike

    def calculate_atm_strike(self, spot_price: Decimal) -> Decimal:
        """
        Rounds underlying spot price to the nearest canonical strike step using standard round-half-up.
        e.g., spot 24524.50 with step 50.0 -> ATM 24500.00
              spot 24525.00 with step 50.0 -> ATM 24550.00
        """
        step = self.config.strike_step
        multiple = (spot_price / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return multiple * step

    def calculate_desired_strikes(self, atm_strike: Decimal, k: Optional[int] = None) -> List[Decimal]:
        """
        Generates list of 2K+1 strikes centered at ATM.
        """
        window_k = k if k is not None else self.config.strike_window_k
        step = self.config.strike_step
        strikes: List[Decimal] = []
        for i in range(-window_k, window_k + 1):
            strike = atm_strike + (Decimal(i) * step)
            strikes.append(strike)
        return strikes

    def get_desired_contracts(
        self,
        spot_price: Decimal,
        as_of_datetime: Optional[datetime] = None
    ) -> List[OptionContractMeta]:
        """
        Resolves the exact list of OptionContractMeta representing the desired universe.
        Includes Primary Active weekly contracts (ATM ±K CE/PE).
        If policy staging time is active on expiry day, includes Next-Weekly contracts (ATM ±3).
        """
        if as_of_datetime is None:
            as_of_datetime = datetime.now(timezone.utc)

        as_of_date = as_of_datetime.date()
        as_of_time = as_of_datetime.time()

        primary_expiry = self.registry.get_nearest_weekly_expiry(
            underlying=self.config.master_name,
            as_of_date=as_of_date
        )
        if primary_expiry is None:
            logger.warning(f"No active unexpired contracts found for {self.config.master_name}")
            return []

        self._current_primary_expiry = primary_expiry
        atm = self.calculate_atm_strike(spot_price)
        primary_strikes = self.calculate_desired_strikes(atm, self.config.strike_window_k)

        contracts: List[OptionContractMeta] = []

        # 1. Primary Active Weekly Contracts
        for strike in primary_strikes:
            for opt_type in ("CE", "PE"):
                contract = self.registry.get_contract(
                    underlying=self.config.master_name,
                    expiry=primary_expiry,
                    strike=strike,
                    option_type=opt_type
                )
                if contract:
                    contracts.append(contract)

        # 2. Configurable Next-Weekly Staging Policy on Expiry Day
        # If today is expiry day and current time >= next_weekly_staging_policy_time (default 13:00 IST)
        if as_of_date == primary_expiry and as_of_time >= self.config.next_weekly_staging_policy_time:
            next_expiry = self.registry.get_next_weekly_expiry(
                underlying=self.config.master_name,
                as_of_date=as_of_date
            )
            if next_expiry:
                staging_strikes = self.calculate_desired_strikes(atm, k=3)
                for strike in staging_strikes:
                    for opt_type in ("CE", "PE"):
                        contract = self.registry.get_contract(
                            underlying=self.config.master_name,
                            expiry=next_expiry,
                            strike=strike,
                            option_type=opt_type
                        )
                        if contract and contract not in contracts:
                            contracts.append(contract)

        return contracts

    def calculate_desired_tokens(
        self,
        spot_price: Decimal,
        as_of_datetime: Optional[datetime] = None
    ) -> Set[int]:
        """Returns set of instrument tokens for the desired universe."""
        contracts = self.get_desired_contracts(spot_price, as_of_datetime)
        return {c.instrument_token for c in contracts}

    def should_rebalance(self, spot_price: Decimal, as_of_datetime: Optional[datetime] = None) -> bool:
        """
        Determines whether universe rebalance calculation is required based on:
        1. Initial state (no previous rebalance spot/ATM recorded).
        2. ATM strike change (e.g. crossing strike midpoint like 24524 -> 24526).
        3. Significant spot drift (spot_drift >= rebalance_threshold_pts).
        4. Expiry day policy staging transition (crossing 13:00 IST).
        5. Expiry roll or primary expiry change.
        """
        if self._last_rebalance_spot is None or self._last_atm_strike is None:
            return True

        current_atm = self.calculate_atm_strike(spot_price)
        if current_atm != self._last_atm_strike:
            return True

        spot_drift = abs(spot_price - self._last_rebalance_spot)
        if spot_drift >= self.config.rebalance_threshold_pts:
            return True

        if as_of_datetime is not None:
            as_of_date = as_of_datetime.date()
            if self._current_primary_expiry is not None:
                # Expiry roll: current date has surpassed the tracked primary expiry
                if as_of_date > self._current_primary_expiry:
                    return True

                # Expiry day staging transition
                if as_of_date == self._current_primary_expiry:
                    if self._last_rebalance_time is not None:
                        last_time = self._last_rebalance_time.time()
                        curr_time = as_of_datetime.time()
                        staging = self.config.next_weekly_staging_policy_time
                        if last_time < staging <= curr_time:
                            return True
                    else:
                        if as_of_datetime.time() >= self.config.next_weekly_staging_policy_time:
                            return True

        return False

    def reconcile(
        self,
        spot_price: Decimal,
        as_of_datetime: Optional[datetime] = None,
        force: bool = False
    ) -> Tuple[Set[int], Set[int]]:
        """
        Reconciles desired tokens against active tokens.
        Returns (to_subscribe, to_unsubscribe).
        """
        if not force and not self.should_rebalance(spot_price, as_of_datetime):
            return set(), set()

        desired = self.calculate_desired_tokens(spot_price, as_of_datetime)
        to_subscribe = desired - self._active_tokens
        to_unsubscribe = self._active_tokens - desired

        return to_subscribe, to_unsubscribe

    def reconcile_against_active(
        self,
        current_active_tokens: Set[int],
        spot_price: Decimal,
        as_of_datetime: Optional[datetime] = None
    ) -> Tuple[Set[int], Set[int]]:
        """
        Directly reconciles the desired token set for the given spot against an external
        set of active tokens (e.g. on WebSocket reconnect or periodic heartbeat audit).
        """
        desired = self.calculate_desired_tokens(spot_price, as_of_datetime)
        to_subscribe = desired - current_active_tokens
        to_unsubscribe = current_active_tokens - desired
        return to_subscribe, to_unsubscribe

    def apply_reconciliation(
        self,
        to_subscribe: Set[int],
        to_unsubscribe: Set[int],
        spot_price: Decimal,
        as_of_datetime: Optional[datetime] = None
    ) -> None:
        """
        Commits reconciliation outcome to active tokens state.
        """
        self._active_tokens.update(to_subscribe)
        self._active_tokens.difference_update(to_unsubscribe)
        self._last_rebalance_spot = spot_price
        self._last_atm_strike = self.calculate_atm_strike(spot_price)
        self._last_rebalance_time = as_of_datetime or datetime.now(timezone.utc)
        logger.info(
            f"Universe reconciled: +{len(to_subscribe)} subscribed, "
            f"-{len(to_unsubscribe)} unsubscribed. Active tokens: {len(self._active_tokens)} "
            f"(ATM: {self._last_atm_strike})"
        )
