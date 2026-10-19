# Nomad Analyst — F&O Quantitative Strategy Evidence Register (Reconciled)

**Document Reference:** `docs/research/fno/fno_strategy_evidence_register.md`  
**Revision Date:** 2026-10-17  
**Auditor:** Quantitative Researcher & Systems Architect  
**Status:** RATIFIED — CANDIDATE STRATEGIES CLASSIFIED STRICTLY AS UNPROVEN HYPOTHESES  

---

## 1. Research Disclaimer & Epistemic Boundaries

### Canonical Specification Reference:
The full data contracts, feature schemas, strategy interfaces, execution models, and evaluation matrix are authoritatively specified in:  
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

### The Fundamental Non-Equivalence Principle
**Underlying index momentum does NOT imply option-buying profitability.**

Empirical evidence demonstrating price persistence in the underlying NIFTY 50 cash index (such as opening range breakouts or VWAP reclaims) **does not prove that buying naked CE or PE options will yield positive risk-adjusted returns**.

In option buying:
1. **Theta Erosion:** Holding a weekly option across 15 to 90 minutes consumes extrinsic value at an accelerating rate, particularly approaching contract expiration.
2. **Volatility Sensitivity (Vega):** A directional move accompanied by declining implied volatility (IV crush) can result in a net loss on a long option even if the underlying moves favorably.
3. **Execution & Statutory Friction:** Crossing the bid-ask spread on entry and exit, plus statutory taxes (0.15% STT on sell-side premium effective 1 April 2026), exchange fees (₹3,553/crore under NSE circular `NSE/FA/73061` effective 1 March 2026: ₹3,552.99 transaction charge + ₹0.01 IPFT), and 18% GST on brokerage, exchange fees, and SEBI charges, creates a severe hurdle rate (~1.5%–3.0% of premium per round trip).

Accordingly, all strategies documented herein are **falsifiable scientific hypotheses to be evaluated prospectively in the Phase 5 parallel paper lab**, not verified profitable systems. **No concrete strategy rules are implemented in Phase 0.**

---

## 2. Hypothesis Register: Candidate Index Option Strategies

### A. Hypothesis FNO-HYP-01: 15-Minute Opening Range Breakout (ORB) with Volume Impulse
- **Conceptual Archetype:** Intraday directional momentum exploitation.
- **Underlying Index Evidence:** Gao et al. (2018, *Journal of Financial Markets*) observe return persistence during early market trading in equity indices following initial price discovery.
- **Option Buying Transferability Hypothesis:**  
  *If the NIFTY 50 cash index breaks cleanly above the 15-minute high (09:15–09:30 IST) with above-average underlying volume ($RVOL \ge 1.3$) and broad equity participation (Advancers $\ge 32$), THEN purchasing the nearest ATM Call option will capture sufficient directional expansion within 15–45 minutes to overcome theta decay and bid-ask spread friction.*
- **Formal Null Hypothesis ($H_0$):**  
  The net post-cost Sharpe ratio of buying ATM CE/PE options on 15m ORB breakouts across a 1-month prospective parallel evaluation window is $\le 0$.
- **Testable Evaluation Framework (Phase 5 Lab):**
  - **Evaluation Window:** 09:30 to 10:30 IST only. No entries permitted after 10:30 IST.
  - **Underlying Condition (Call):** Spot close on 1-minute candle $> \text{High}_{09:15-09:30} + 0.05\%$.
  - **Confirmation Filters:** NIFTY 5-minute relative volume $RVOL \ge 1.3$; market breadth $\ge 32$ advancers; India VIX daily change between $-5\%$ and $+10\%$.
  - **Option Contract Selection:** Active weekly expiry resolved authoritatively from the instrument master CSV, nearest ATM strike ($\text{Delta} \approx 0.50$).
  - **Execution Fill Model:** Taker order filled at `Best Ask + Slippage` (0.5% premium slippage).
  - **Deterministic Exit Rules:** Profit Target $+25\%$ on premium; Stop Loss $-15\%$ on premium; Time Stop 45 minutes or 11:15 IST.
- **Falsification & Rejection Gates (Phase 6):**
  Reject hypothesis if after the 1-month parallel experiment:
  - Net Profit Factor (accounting for fees and slippage) $< 1.25$.
  - Maximum Drawdown exceeds $15\%$ of allocated margin.
  - Friction Drag Ratio $\ge 35\%$ of gross profits.
  - Sample size $N < 20$ trades.

---

### B. Hypothesis FNO-HYP-02: Intraday VWAP Reclaim & Continuation
- **Conceptual Archetype:** Institutional mean-reversion recovery into continuation.
- **Underlying Index Evidence:** Algorithmic execution literature demonstrates that institutional liquidity clusters around volume-weighted average price (VWAP) benchmarks.
- **Option Buying Transferability Hypothesis:**  
  *When NIFTY pulls back to its session VWAP between 10:30 and 13:30 IST and reclaims the benchmark on expanding volume with breadth support, purchasing ATM options captures a secondary momentum wave with tight risk definition.*
- **Formal Null Hypothesis ($H_0$):**  
  The net post-cost return of ATM options bought on VWAP reclaims across a 1-month prospective parallel evaluation window is statistically indistinguishable from zero or negative.
- **Testable Evaluation Framework (Phase 5 Lab):**
  - **Evaluation Window:** 10:30 to 13:30 IST.
  - **Underlying Condition (Call):** Spot trades below session VWAP for $\ge 3$ consecutive 5-minute bars, then closes above VWAP with a 5-minute candle body $> 0.08\%$.
  - **Confirmation Filters:** 5-minute candle volume $> 1.2 \times$ 20-period volume SMA; Advance/Decline ratio aligned with breakout direction; Option bid-ask spread $\le 1.5\%$ of option premium.
  - **Deterministic Exit Rules:** Profit Target $+20\%$ on premium; Stop Loss spot closes below VWAP by $> 0.10\%$ or $-12\%$ on premium; Time Stop mandatory exit at 14:30 IST.
- **Falsification & Rejection Gates (Phase 6):**
  Reject hypothesis if after the 1-month parallel experiment:
  - Net Profit Factor $< 1.25$.
  - Friction Drag Ratio $\ge 35\%$.
  - Loss rate due to mid-day chop/theta exceeds $60\%$.

---

### C. Hypothesis FNO-HYP-03: Volatility Squeeze & Bollinger Expansion
- **Status:** **EXCLUDED FROM SCOPE / DEFERRED TO FUTURE RESEARCH.**
- **Reason for Exclusion:** Prolonged volatility squeezes induce severe theta decay in long options while awaiting expansion. Cannot be reliably evaluated without accumulated historical options datasets.

---

## 3. Comparison of Empirical Evidence vs. Theoretical Assumptions

| Dimension | Underlying Cash Index (`^NSEI`) | Long ATM Index Options (`NIFTY CE/PE`) | Evidence Status |
| :--- | :--- | :--- | :--- |
| **Price Persistence (Momentum)** | Verified in financial literature (Gao et al., 2018; Baltussen et al., 2021). | **Unproven.** Directional gain can be offset by IV decline or theta loss. | Empirical study required on live prospective data. |
| **Holding Time Impact** | Linear carry; no deterministic expiration. | **Severe non-linear decay.** Extrinsic value decays to 0 at $t \to T$. | Verified mathematical property ($\Theta < 0$). |
| **Transaction Frictions** | Cash equities: minimal slippage on NIFTY constituents (~0.02%). | High relative spread: ₹1.00 spread on ₹80 premium = **1.25% drag** per side. | Verified market microstructure property. |
| **Tax & Fee Frictions** | Standard STT rates. | Higher effective drag: STT 0.15% on sell premium (effective 1 April 2026) + NSE charges ₹3,553/crore (Circular `NSE/FA/73061` effective 1 March 2026: ₹3,552.99 exchange fee + ₹0.01 IPFT) + GST on brokerage, exchange fees, and SEBI charges. | Verified regulatory rates (SEBI 2026 studies). |

---

## 4. Prospective Lab Data Requirements to Validate Hypotheses

To test `FNO-HYP-01` and `FNO-HYP-02` without speculation in the Phase 5 prospective paper lab:
1. **Synchronized 1-minute OHLCV bars** for both the underlying index (`^NSEI`) and active ATM/ITM/OTM option contracts.
2. **Best Bid and Best Ask quotes** recorded at signal generation to compute exact spread drag.
3. **Open Interest (OI) changes** across consecutive 1-minute bars to measure participation.
4. **Calculated Implied Volatility (IV)** to isolate Vega expansion/crush from directional Delta gains.
5. **Multi-Metric Decision Matrix:** Strategies evaluated across gross expectancy, friction drag ratios, profit factor, drawdown, and statistical uncertainty ($t$-statistic). Anti-curve-fitting rule strictly enforced: no winner selected on total P&L alone.
