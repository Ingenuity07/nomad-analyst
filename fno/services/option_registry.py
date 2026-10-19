"""
F&O Option Instrument Registry & Universe Discovery Service.
Authoritative parsing of Zerodha Kite Connect instrument master for NFO options.
"""

import csv
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_MASTER_CACHE_FILE = Path("data/universe/kite_instruments_master.csv")


class StaleMasterFileError(Exception):
    """Raised when the instrument master CSV exceeds acceptable freshness threshold."""
    pass


@dataclass
class UnderlyingAssetConfig:
    """Generic configuration for an underlying asset's derivative universe."""
    underlying_symbol: str              # e.g., "^NSEI", "^NSEBANK"
    underlying_name: str                # e.g., "NIFTY 50", "NIFTY BANK"
    master_name: str                    # e.g., "NIFTY", "BANKNIFTY" in broker master CSV
    futures_symbol: Optional[str] = None # e.g., "NIFTY-FUT" for active near-month
    exchange: str = "NFO"
    strike_step: Decimal = Decimal("50.0")
    lot_size: int = 25
    tick_size: Decimal = Decimal("0.05")
    strike_window_k: int = 5            # ATM ±K strikes (default 5 -> 11 CE + 11 PE = 22 strikes)
    rebalance_threshold_pts: Decimal = Decimal("50.0")
    
    # Configurable Operational & Risk Policies
    next_weekly_staging_policy_time: time = time(13, 0)
    intraday_square_off_policy_time: time = time(15, 15)
    session_close_time: time = time(15, 30)
    is_active: bool = True
    initial_spot_estimate: Optional[Decimal] = None


# Preconfigured Default Underlying Configs
CONFIG_NIFTY = UnderlyingAssetConfig(
    underlying_symbol="^NSEI",
    underlying_name="NIFTY 50",
    master_name="NIFTY",
    futures_symbol="NIFTY-FUT",
    exchange="NFO",
    strike_step=Decimal("50.0"),
    lot_size=25,
    tick_size=Decimal("0.05"),
    strike_window_k=5,
    rebalance_threshold_pts=Decimal("50.0"),
    initial_spot_estimate=Decimal("24500.0"),
)


@dataclass(frozen=True)
class OptionContractMeta:
    """Metadata representing an active NFO option contract."""
    instrument_token: int
    exchange_token: int
    tradingsymbol: str
    name: str                           # e.g. "NIFTY"
    expiry: date                        # Authoritative expiry date from master
    strike: Decimal
    tick_size: Decimal
    lot_size: int
    instrument_type: str                # "CE" or "PE"
    segment: str                        # "NFO-OPT"
    exchange: str                       # "NFO"


class OptionInstrumentRegistry:
    """
    Manages loading, validation, and querying of active NFO option instruments.
    Guarantees that the broker master CSV is the authoritative source of expiry dates.
    """

    def __init__(self, master_path: Optional[Union[str, Path]] = None):
        self.master_path = Path(master_path or DEFAULT_MASTER_CACHE_FILE)
        self._token_map: Dict[int, OptionContractMeta] = {}
        self._symbol_map: Dict[str, OptionContractMeta] = {}
        # Key: (name, expiry) -> list of contracts
        self._name_expiry_map: Dict[Tuple[str, date], List[OptionContractMeta]] = {}
        # Key: (name, expiry, strike, option_type) -> contract
        self._lookup_map: Dict[Tuple[str, date, Decimal, str], OptionContractMeta] = {}
        # Key: name -> sorted list of unique expiry dates
        self._name_expiries: Dict[str, List[date]] = {}
        self._loaded_at: Optional[datetime] = None
        self._master_mtime: Optional[datetime] = None
        self._is_stale: bool = False

    @property
    def is_stale(self) -> bool:
        return self._is_stale

    @property
    def master_mtime(self) -> Optional[datetime]:
        return self._master_mtime

    def is_master_stale(self, max_age_hours: int = 24) -> bool:
        """Checks if the master CSV file is older than max_age_hours."""
        if not self.master_path.exists():
            return True
        mtime = datetime.fromtimestamp(self.master_path.stat().st_mtime, tz=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - mtime).total_seconds()
        return age_seconds > (max_age_hours * 3600)

    def load_master(
        self, 
        max_age_hours: int = 24, 
        raise_if_stale: bool = False,
        force_reload: bool = False
    ) -> int:
        """
        Parses the master CSV, indexing all NFO options.
        Returns the number of NFO option contracts indexed.
        """
        if self._token_map and not force_reload:
            return len(self._token_map)

        if not self.master_path.exists():
            raise FileNotFoundError(f"Kite instrument master CSV not found at {self.master_path}")

        mtime = datetime.fromtimestamp(self.master_path.stat().st_mtime, tz=timezone.utc)
        self._master_mtime = mtime
        age_seconds = (datetime.now(timezone.utc) - mtime).total_seconds()
        self._is_stale = age_seconds > (max_age_hours * 3600)

        if self._is_stale:
            msg = (
                f"Kite instrument master file at {self.master_path} is stale "
                f"(age: {age_seconds / 3600:.1f}h > {max_age_hours}h limit)."
            )
            logger.warning(msg)
            if raise_if_stale:
                raise StaleMasterFileError(msg)

        # Clear existing mappings
        self._token_map.clear()
        self._symbol_map.clear()
        self._name_expiry_map.clear()
        self._lookup_map.clear()
        self._name_expiries.clear()

        expiries_set: Dict[str, Set[date]] = {}

        with open(self.master_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter strictly for NFO options
                if row.get("exchange") != "NFO" or row.get("segment") != "NFO-OPT":
                    continue

                try:
                    token = int(row["instrument_token"])
                    ex_token = int(row["exchange_token"])
                    tradingsymbol = row["tradingsymbol"].strip()
                    name = row["name"].strip().strip('"')
                    expiry_str = row["expiry"].strip()
                    if not expiry_str:
                        continue
                    expiry = date.fromisoformat(expiry_str)
                    strike = Decimal(row["strike"])
                    tick_size = Decimal(row["tick_size"])
                    lot_size = int(row["lot_size"])
                    inst_type = row["instrument_type"].strip().upper()
                    segment = row["segment"].strip()
                    exchange = row["exchange"].strip()

                    meta = OptionContractMeta(
                        instrument_token=token,
                        exchange_token=ex_token,
                        tradingsymbol=tradingsymbol,
                        name=name,
                        expiry=expiry,
                        strike=strike,
                        tick_size=tick_size,
                        lot_size=lot_size,
                        instrument_type=inst_type,
                        segment=segment,
                        exchange=exchange,
                    )

                    self._token_map[token] = meta
                    self._symbol_map[tradingsymbol] = meta
                    self._lookup_map[(name, expiry, strike, inst_type)] = meta

                    if (name, expiry) not in self._name_expiry_map:
                        self._name_expiry_map[(name, expiry)] = []
                    self._name_expiry_map[(name, expiry)].append(meta)

                    if name not in expiries_set:
                        expiries_set[name] = set()
                    expiries_set[name].add(expiry)

                except (ValueError, KeyError) as e:
                    logger.debug(f"Skipping malformed NFO option row: {row}. Error: {e}")
                    continue

        # Sort expiries chronologically
        for name, exp_set in expiries_set.items():
            self._name_expiries[name] = sorted(list(exp_set))

        self._loaded_at = datetime.now(timezone.utc)
        logger.info(
            f"OptionInstrumentRegistry loaded {len(self._token_map)} NFO options "
            f"across {len(self._name_expiries)} underlyings from {self.master_path}."
        )
        return len(self._token_map)

    def get_by_token(self, instrument_token: int) -> Optional[OptionContractMeta]:
        """Look up contract metadata by broker instrument token."""
        return self._token_map.get(instrument_token)

    # Alias for contract token lookup
    get_contract_by_token = get_by_token

    def get_by_tradingsymbol(self, tradingsymbol: str) -> Optional[OptionContractMeta]:
        """Look up contract metadata by broker tradingsymbol."""
        return self._symbol_map.get(tradingsymbol)

    def get_active_expiries(
        self, 
        underlying: str = "NIFTY", 
        as_of_date: Optional[date] = None
    ) -> List[date]:
        """
        Returns sorted list of active (unexpired) expiries for the given underlying.
        Treats the CSV's expiry column as the sole authoritative source of truth.
        """
        all_expiries = self._name_expiries.get(underlying, [])
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc).date()
        return [exp for exp in all_expiries if exp >= as_of_date]

    def get_nearest_weekly_expiry(
        self, 
        underlying: str = "NIFTY", 
        as_of_date: Optional[date] = None
    ) -> Optional[date]:
        """
        Returns the closest upcoming expiry date for the underlying (Primary Active).
        """
        active = self.get_active_expiries(underlying=underlying, as_of_date=as_of_date)
        return active[0] if active else None

    def get_next_weekly_expiry(
        self, 
        underlying: str = "NIFTY", 
        as_of_date: Optional[date] = None
    ) -> Optional[date]:
        """
        Returns the second upcoming expiry date for the underlying (Next-Weekly).
        """
        active = self.get_active_expiries(underlying=underlying, as_of_date=as_of_date)
        return active[1] if len(active) > 1 else None

    def get_contracts_for_expiry(
        self, 
        underlying: str = "NIFTY", 
        expiry: Optional[date] = None
    ) -> List[OptionContractMeta]:
        """Returns all contracts (CE and PE) for a specific underlying and expiry date."""
        if expiry is None:
            expiry = self.get_nearest_weekly_expiry(underlying=underlying)
        if expiry is None:
            return []
        return self._name_expiry_map.get((underlying, expiry), [])

    def get_contract(
        self, 
        underlying: str, 
        expiry: date, 
        strike: Union[Decimal, float, int], 
        option_type: str
    ) -> Optional[OptionContractMeta]:
        """Look up a specific strike contract."""
        strike_dec = Decimal(str(strike))
        opt_type = option_type.upper().strip()
        return self._lookup_map.get((underlying, expiry, strike_dec, opt_type))
