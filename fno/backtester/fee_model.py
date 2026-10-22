"""
Nomad Analyst — Effective-Dated Historical Statutory Fee Calculator
Reference: DEC-02 in docs/historical_options_backtester_architecture.md
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fno.execution.fee_calculator import StatutoryFeeBreakdown


class HistoricalFeeCalculator:
    """
    Computes effective-dated statutory fees, taxes, and broker charges for historical NFO trades.
    Supports Regime 1 (pre-April 2026 STT: 0.10%) and Regime 2 (post-April 2026 STT: 0.15%).
    """

    REGIME_CUTOFF_DATE = date(2026, 4, 1)

    FLAT_BROKERAGE_PER_ORDER = Decimal("20.00")
    EXCHANGE_TURNOVER_RATE = Decimal("0.0003553")  # 0.03553% (NSE/FA/73061 unified)
    SEBI_TURNOVER_RATE = Decimal("0.000001")       # 0.0001% (₹10/crore)
    STAMP_DUTY_BUY_RATE = Decimal("0.00003")       # 0.003%
    GST_RATE = Decimal("0.18")                     # 18% on (Brokerage + Exchange + SEBI)

    # STT Rates by Regime
    REGIME_1_STT_SELL_RATE = Decimal("0.0010")     # 0.10% (Finance (No. 2) Act 2024)
    REGIME_2_STT_SELL_RATE = Decimal("0.0015")     # 0.15% (Finance Act 2026)

    # STT on Exercise Settlement (Intrinsic Value)
    REGIME_1_STT_EXERCISE_RATE = Decimal("0.00125") # 0.125%
    REGIME_2_STT_EXERCISE_RATE = Decimal("0.0015")  # 0.15%

    @classmethod
    def round_paisa(cls, amount: Decimal) -> Decimal:
        """Rounds amount strictly to the nearest paisa (0.01)."""
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def get_stt_rates_for_date(cls, trade_date: date, is_exercise: bool = False) -> Decimal:
        """Resolves applicable STT rate based on trade date and exercise status."""
        if trade_date < cls.REGIME_CUTOFF_DATE:
            return cls.REGIME_1_STT_EXERCISE_RATE if is_exercise else cls.REGIME_1_STT_SELL_RATE
        return cls.REGIME_2_STT_EXERCISE_RATE if is_exercise else cls.REGIME_2_STT_SELL_RATE

    @classmethod
    def calculate_round_trip(
        cls,
        buy_price: Decimal,
        sell_price: Decimal,
        quantity: int,
        trade_date: date,
        is_exercise_settlement: bool = False,
        custom_brokerage_per_order: Optional[Decimal] = None,
    ) -> StatutoryFeeBreakdown:
        """
        Calculates all statutory fees and taxes across a complete round-trip trade.
        For exercised ITM settlements, STT applies to intrinsic settlement value.
        For worthless expired options (sell_price = 0.00), sell turnover is 0 and no STT applies.
        """
        qty_dec = Decimal(str(quantity))
        buy_turnover = cls.round_paisa(buy_price * qty_dec)
        sell_turnover = cls.round_paisa(sell_price * qty_dec)

        brokerage_rate = custom_brokerage_per_order or cls.FLAT_BROKERAGE_PER_ORDER

        # 1. Brokerage:
        # If expired worthless at 0.00 in exercise settlement, only entry order leg was placed
        if is_exercise_settlement and sell_price == Decimal("0.00"):
            brokerage = brokerage_rate
        else:
            brokerage = brokerage_rate * Decimal("2.0")

        # 2. Exchange Turnover Charges:
        exch_charges = cls.round_paisa((buy_turnover + sell_turnover) * cls.EXCHANGE_TURNOVER_RATE)

        # 3. SEBI Turnover Charges:
        sebi_charges = cls.round_paisa((buy_turnover + sell_turnover) * cls.SEBI_TURNOVER_RATE)

        # 4. Stamp Duty (buy leg only):
        stamp_duty = cls.round_paisa(buy_turnover * cls.STAMP_DUTY_BUY_RATE)

        # 5. STT:
        stt_rate = cls.get_stt_rates_for_date(trade_date, is_exercise=is_exercise_settlement)
        if sell_turnover > Decimal("0.00"):
            stt = cls.round_paisa(sell_turnover * stt_rate)
        else:
            stt = Decimal("0.00")

        # 6. GST: 18% strictly on (Brokerage + Exchange + SEBI)
        gst_base = brokerage + exch_charges + sebi_charges
        gst = cls.round_paisa(gst_base * cls.GST_RATE)

        statutory_levies = exch_charges + sebi_charges + stamp_duty + stt + gst
        total_frictions = brokerage + statutory_levies

        regime_label = "REGIME_1_PRE_APRIL_2026 (STT: 0.10%)" if trade_date < cls.REGIME_CUTOFF_DATE else "REGIME_2_POST_APRIL_2026 (STT: 0.15%)"

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
            effective_schedule_date="2024-10-01" if trade_date < cls.REGIME_CUTOFF_DATE else "2026-04-01",
            broker_name="DISCOUNT_FLAT_DEFAULT",
            fee_model_label=regime_label,
        )
