"""
Nomad Analyst — Statutory Fee & Tax Calculator for Indian Equity Options (NFO)
Reference: Phase 22D Specification (docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

Authoritative, effective-dated fee schedules (Current Schedule: 2026-04-01):
1. Broker-Specific Commercial Brokerage:
   - Discount flat rate: ₹20.00 flat per executed order leg.
2. Statutory Levies & Regulatory Charges:
   - Exchange Turnover Charges: 0.03553% (NSE Circular NSE/FA/73061, effective 1 March 2026, including IPFT).
   - Securities Transaction Tax (STT): 0.15% on sell-side premium turnover, or 0.15% on intrinsic settlement value for exercised ITM options upon expiration (Finance Act 2026, effective 1 April 2026).
   - Goods & Services Tax (GST): 18% applied strictly to taxable services base: (Brokerage + Exchange Charges + SEBI Charges). STT and Stamp Duty are taxes and strictly exempt from GST.
   - SEBI Turnover Charges: 0.0001% (₹10/crore).
   - Stamp Duty: 0.003% on buy-side premium turnover only (Indian Stamp Act).

Unsupported Dates & Settlement Assumptions:
- Pre-2026-03-01 trades operated under tiered NSE turnover slabs (not unified ₹3,553/crore) and pre-April 2026 STT (0.0625% or 0.10%).
- Settlement Model: NIFTY index options are strictly European-style and cash-settled against the official index closing value. Physical delivery is NOT applicable.
All figures calculated and rounded strictly to the exact paisa (Decimal 0.01).
"""

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


@dataclass(frozen=True)
class StatutoryFeeBreakdown:
    buy_turnover: Decimal
    sell_turnover: Decimal
    brokerage: Decimal                  # Broker-specific commercial fee
    exchange_charges: Decimal           # Statutory: NSE + IPFT
    stt: Decimal                        # Statutory: Securities Transaction Tax
    sebi_charges: Decimal               # Statutory: SEBI turnover charge
    stamp_duty: Decimal                 # Statutory: Indian Stamp Duty (buy side)
    gst: Decimal                        # Statutory: 18% on (Brokerage + Exchange + SEBI)
    statutory_levies: Decimal           # Sum of all non-brokerage government/exchange levies
    total_frictions: Decimal            # Brokerage + statutory_levies
    effective_schedule_date: str = "2026-04-01"
    broker_name: str = "DISCOUNT_FLAT_DEFAULT"
    fee_model_label: str = "STRESS_TEST_FEE_SCHEDULE_2026 (STT: 0.15% Stress vs 0.10% Statutory)"

    def to_dict(self) -> Dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items()}


class StatutoryFeeCalculator:
    """
    Computes effective-dated transaction fees and taxes for NFO options.
    Distinguishes broker-specific commercial fees from statutory charges.
    Explicitly separates legal statutory baseline rates from conservative stress assumptions.
    """

    EFFECTIVE_SCHEDULE_DATE = "2026-04-01"
    EARLIEST_SUPPORTED_DATE = date(2026, 4, 1)
    FLAT_BROKERAGE_PER_ORDER = Decimal("20.00")
    EXCHANGE_TURNOVER_RATE = Decimal("0.0003553")  # 0.03553% (NSE/FA/73061)
    SEBI_TURNOVER_RATE = Decimal("0.000001")       # 0.0001% (₹10/crore)
    STAMP_DUTY_BUY_RATE = Decimal("0.00003")       # 0.003%

    # STT Rates: Legal statutory rate vs. Conservative stress scenario
    STATUTORY_STT_SELL_RATE = Decimal("0.0010")  # 0.10% legal statutory rate (Finance (No. 2) Act 2024, eff 2024-10-01)
    STRESS_STT_SELL_RATE = Decimal("0.0015")     # 0.15% conservative stress scenario (+50% friction drag)
    STT_SELL_RATE = STRESS_STT_SELL_RATE         # Active trial model: conservative stress scenario

    GST_RATE = Decimal("0.18")                     # 18%
    SCHEDULE_LABEL = "STRESS_TEST_FEE_SCHEDULE_2026 (STT: 0.15% Stress vs 0.10% Statutory)"

    @classmethod
    def round_paisa(cls, amount: Decimal) -> Decimal:
        """Rounds amount to the nearest paisa (0.01)."""
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_round_trip(
        cls,
        buy_price: Decimal,
        sell_price: Decimal,
        quantity: int,
        is_exercise_settlement: bool = False,
        custom_brokerage_per_order: Optional[Decimal] = None,
        trade_date: Optional[date] = None,
        allow_default_schedule: bool = False,
    ) -> StatutoryFeeBreakdown:
        """
        Calculates all statutory fees and taxes across a complete round-trip trade.
        For exercised ITM settlements, STT applies at 0.15% to intrinsic settlement value.
        For worthless expired options, sell turnover is 0 and no STT applies.

        Policy for trade_date:
        - If trade_date is None and allow_default_schedule is False, raises ValueError.
          Silent fallback to a default schedule is prohibited.
        - If allow_default_schedule is True and trade_date is None, explicitly adopts
          the default schedule (EFFECTIVE_SCHEDULE_DATE = '2026-04-01').
        - If trade_date is provided, it must be >= EARLIEST_SUPPORTED_DATE (2026-04-01).
        """
        if trade_date is None:
            if not allow_default_schedule:
                raise ValueError(
                    "Missing trade_date: An explicit trade_date is required to evaluate statutory fee schedules. "
                    "Silent default schedule selection is prohibited. Pass trade_date (>= 2026-04-01) or set "
                    f"allow_default_schedule=True to explicitly use schedule {cls.EFFECTIVE_SCHEDULE_DATE}."
                )
        elif trade_date < cls.EARLIEST_SUPPORTED_DATE:
            raise ValueError(
                f"Historical trade date {trade_date} is unsupported. Statutory schedule is configured "
                f"for effective date {cls.EFFECTIVE_SCHEDULE_DATE} onwards (NSE Circular NSE/FA/73061 "
                f"& Finance Act 2026). Earlier dates used tiered exchange slabs and lower STT rates."
            )
        qty_dec = Decimal(str(quantity))
        buy_turnover = cls.round_paisa(buy_price * qty_dec)
        sell_turnover = cls.round_paisa(sell_price * qty_dec)

        brokerage_rate = custom_brokerage_per_order or cls.FLAT_BROKERAGE_PER_ORDER

        # 1. Broker-specific Brokerage:
        # Note: If expired worthless at 0, no broker sell order executed on exchange
        if is_exercise_settlement and sell_price == Decimal("0.00"):
            brokerage = brokerage_rate  # Entry order only
        else:
            brokerage = brokerage_rate * Decimal("2.0")

        # 2. Exchange Turnover Charges: on both buy and sell premium
        exch_charges = cls.round_paisa((buy_turnover + sell_turnover) * cls.EXCHANGE_TURNOVER_RATE)

        # 3. SEBI Turnover Charges: on total premium turnover
        sebi_charges = cls.round_paisa((buy_turnover + sell_turnover) * cls.SEBI_TURNOVER_RATE)

        # 4. Stamp Duty: 0.003% on buy leg only
        stamp_duty = cls.round_paisa(buy_turnover * cls.STAMP_DUTY_BUY_RATE)

        # 5. STT:
        # Sell leg at 0.15% on premium or intrinsic settlement
        if sell_turnover > Decimal("0.00"):
            stt = cls.round_paisa(sell_turnover * cls.STT_SELL_RATE)
        else:
            stt = Decimal("0.00")

        # 6. GST: 18% strictly on (Brokerage + Exchange Charges + SEBI Charges)
        gst_base = brokerage + exch_charges + sebi_charges
        gst = cls.round_paisa(gst_base * cls.GST_RATE)

        statutory_levies = exch_charges + sebi_charges + stamp_duty + stt + gst
        total_frictions = brokerage + statutory_levies

        return StatutoryFeeBreakdown(
            buy_turnover=buy_turnover,
            sell_turnover=sell_turnover,
            brokerage=brokerage,
            exchange_charges=exch_charges,
            stt=stt,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            statutory_levies=statutory_levies,
            total_frictions=total_frictions,
            effective_schedule_date=cls.EFFECTIVE_SCHEDULE_DATE,
            fee_model_label=cls.SCHEDULE_LABEL,
        )
