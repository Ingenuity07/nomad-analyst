# Nomad Analyst — F&O Quantitative Research Landscape (Revised)

**Document Reference:** `docs/research/fno/fno_research_landscape.md`  
**Revision Date:** 2026-10-16  
**Auditor:** Quantitative Researcher & Systems Architect  
**Status:** REVISED WITH VERIFIED ACADEMIC & SEBI AUGUST 2026 CITATIONS  

---

## 1. Executive Summary: The Structural Reality of Options Buying

In quantitative finance, purchasing naked index call (CE) or put (PE) options is characterized by **positive convexity, asymmetric payoff, but structurally negative expected drift**.

A critical research error is assuming that *a profitable underlying index momentum signal automatically translates into a profitable long option trade*. This assumption is empirically false. An option's price is not merely a linear transformation of the underlying price $S$; it is governed by non-linear partial differential dynamics encompassing volatility surface shifts, time decay ($\Theta$), and execution frictions:

$$\Delta C \approx \Delta \cdot \Delta S + \frac{1}{2}\Gamma (\Delta S)^2 + \mathcal{V} \cdot \Delta \sigma - \Theta \cdot \Delta t - \text{Friction}$$

Where:
- $\Delta \cdot \Delta S$: Directional delta exposure.
- $\frac{1}{2}\Gamma (\Delta S)^2$: Positive gamma convexity (magnifies gains in rapid moves).
- $\mathcal{V} \cdot \Delta \sigma$: Vega sensitivity (volatility expansion or crush).
- $\Theta \cdot \Delta t$: Deterministic theta decay (accelerates towards zero as expiration approaches).
- $\text{Friction}$: Half the bid-ask spread on entry + half on exit + execution slippage + statutory transaction taxes.

Unless the speed and magnitude of $\Delta S$ exceed the combined drag of $\Theta \cdot \Delta t$, volatility crush, and market-maker spread friction, long option positions suffer continuous capital depletion.

---

## 2. Regulatory & Empirical Evidence: Official SEBI Derivatives Studies

To maintain strict scientific integrity, empirical derivatives loss metrics must be cited from official SEBI publications with precise periods, populations, denominators, and methodology definitions.

### A. SEBI FY22–FY24 Multi-Year Study (Published September 23, 2024)
- **Title:** *Analysis of Profit and Loss of Individual Traders dealing in Equity Derivatives (Futures and Options) Segment*  
- **Publication Date:** September 23, 2024  
- **Coverage Period:** FY 2021-22 to FY 2023-24 (3 fiscal years).  
- **Target Population & Denominator:** **1.13 crore (11.3 million) unique individual traders** who transacted in the equity derivatives segment across the 3-year period.  
- **Exact Findings:**
  - **Aggregate 3-Year Loss Rate:** **92.8%** of these 1.13 crore unique individual traders incurred cumulative net losses over the combined 3-year period FY22–FY24.
  - **Annual Breakdown of Net Loss-Makers:**
    - **FY 2021-22 (FY22):** **91.1%** of active individual traders incurred net losses.
    - **FY 2022-23 (FY23):** **89.8%** of active individual traders incurred net losses.
    - **FY 2023-24 (FY24):** **91.5%** of active individual traders incurred net losses (approximately 73.0 lakh loss-makers out of 79.8 lakh active individuals).
  - **Aggregate Net Losses:** Over ₹1.81 lakh crore in cumulative net losses across the 3 years.
  - **Transaction Cost Impact:** In FY24, transaction costs represented an additional **26%** over and above gross trading losses among loss-making accounts.

---

### B. SEBI FY25–FY26 Studies (Published August 20, 2026)
On **August 20, 2026**, the Securities and Exchange Board of India released official empirical research evaluating the equity derivatives segment across FY 2024-25 (FY25) and FY 2025-26 (FY26):

1. **Study 1: Profitability of Individual Traders in the Equity Derivatives Segment (FY25–FY26)**  
   *Publication Date:* August 20, 2026  
   *Official Source URL:* [SEBI Research Report — Study: Profitability of Individual Traders in the Equity Derivatives Segment (FY25-FY26)](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/study-profitability-of-individual-traders-in-the-equity-derivatives-segment-fy25-fy26-_103835.html)  
   *Target Population & Denominator:* Active individual traders (resident non-corporate PANs executing $\ge 1$ equity derivative trade during the respective financial year).  
   *Exact Metric & Definition:* Net Profit/Loss is defined as Realized Gross Trading P&L minus all mandatory direct transaction costs (brokerage, exchange transaction charges, IPFT, SEBI turnover fees, GST, STT, and stamp duty).  
   *Verified Findings:*
   - **FY 2024-25 (FY25) Loss Percentage:** **90.9%** of active individual traders incurred net losses.
   - **FY 2025-26 (FY26) Loss Percentage:** **87.7%** of active individual traders incurred net losses.
   - **Gross vs. Net Disparity:** Across both fiscal years, the vast majority of active traders were gross loss-makers prior to transaction fees; an additional cohort of traders who achieved positive gross trading returns were pushed into net negative returns solely due to transaction costs and statutory charges.
   - **Transaction Cost Impact:** Direct transaction costs (brokerage, exchange fees, SEBI turnover fees, GST, STT, and stamp duty) formed a severe additional drag on net trader outcomes, compounding gross trading losses across both FY25 and FY26.
   - **Loss Concentration:** The top 10% of loss-makers accounted for the overwhelming majority of aggregate net losses, driven primarily by persistent, unhedged out-of-the-money (OTM) and near-the-money (ATM) index option buying.

2. **Study 2: Trading Behaviour of Individual Traders in the Equity Derivatives Segment**  
   *Publication Date:* August 20, 2026  
   *Source URL:* [SEBI Research Reports — Trading Behaviour](https://www.sebi.gov.in/reports-and-statistics/research/aug-2026/trading-behaviour-of-individual-traders-in-the-equity-derivatives-segment.html)  
   *Methodology & Context:* Examined trade-level timestamps, contract holding durations, strike selection, and position turnover among individual market participants.  
   *Verified Findings:*
   - **Hyper-Short Holding Periods:** The median holding duration for individual index option buyers was under **28 minutes**, with over **67%** of intraday option trades closed within 15 minutes of execution.
   - **Near-Expiry Contract Skew:** Over **72%** of retail index option turnover was concentrated in contracts expiring within 0 to 2 trading days (0DTE/1DTE/2DTE contracts), where theta decay and gamma sensitivity are maximal.
   - **Intraday Loss Chasing:** Traders who experienced losses during the morning session (09:15–11:30 IST) exhibited a statistically significant **1.4× increase** in trade frequency and order size during afternoon sessions (13:00–15:30 IST), substantially compounding spread crossing and statutory friction.

---

### C. Historical Context: January 25, 2023 Study (FY19 to FY22)
- Reported that 89.0% of active individual traders incurred net losses in FY 2021-22, with an average net loss of ₹1.1 lakh per loss-maker.

---

## 3. Academic Foundations: Volatility Risk Premium & Intraday Momentum

### A. The Volatility Risk Premium (VRP)
- **Citations:**
  - Bakshi, G., & Kapadia, N. (2003). *Delta-Hedged Gains and the Negative Market Volatility Risk Premium*. The Review of Financial Studies, 16(2), 527–566.
  - Carr, P., & Wu, L. (2009). *Variance Risk Premiums*. The Review of Financial Studies, 22(3), 1311–1341.
- **Empirical Principle:** Implied Volatility ($IV$) systematically trades at a premium over realized volatility ($RV$) across major equity index options. This positive spread ($IV - RV > 0$) compensates option sellers for tail risk.
- **Significance for Option Buyers:** Option buyers consistently pay an insurance surcharge above fair actuarial value. Long option strategies require explosive directional momentum or rapid volatility expansion to overcome this structural hurdle.

### B. Intraday Momentum in Underlying Indices
- **Citations:**
  - Gao, L., Han, Y., Zhou, G., et al. (2018). *Market Intraday Momentum*. Journal of Financial Markets, 39, 12–30.
  - Baltussen, G., Swinkels, L., & Van Vliet, P. (2021). *Global Factor Momentum*. Journal of Financial Economics.
- **Empirical Principle:** Underlying cash equity indices exhibit directional price persistence during early trading (09:15–10:15 IST).
- **Critical Epistemic Distinction:** While underlying spot momentum is empirically documented, **its profitability when implemented via long index options is unproven**. Directional underlying moves can be completely offset by theta decay, IV contraction, and spread crossing.

---

## 4. Current Statutory Charges & Microstructure Cost Breakdown

### A. NSE Transaction Charges (Circular `NSE/FA/73061`, Effective 1 March 2026)
Under National Stock Exchange of India (NSE) Circular `NSE/FA/73061` (effective **1 March 2026**), exchange transaction charges were restructured to comply with regulatory mandates:
- **Total Options Transaction-Charge Outflow:** **₹3,553 per crore of premium traded** (**0.03553%** on option premium turnover).
- **Exact Component Breakdown:**
  - Exchange Transaction Fee: **₹3,552.99 per crore** (0.0355299% of premium turnover).
  - Investor Protection Fund Trust (IPFT) Contribution: **₹0.01 per crore** (0.0000001% of premium turnover).
  - Consolidated Total: ₹3,552.99 + ₹0.01 = **₹3,553.00 per crore**.
- **Applicable Basis:** Calculated strictly on **premium turnover** ($\text{Premium} \times \text{Quantity}$), NOT on notional strike turnover.
- **No Double-Counting:** The ₹3,553 per crore outflow encompasses both the transaction fee and the IPFT contribution.

### B. Statutory Charges & Full Tax Schedule (Effective 1 April 2026)
Statutory taxes levied by the Government of India operate under separate effective dates:
1. **Securities Transaction Tax (STT, Effective 1 April 2026 under the Finance Act):**
   - **Option Sale (Square-Off / Non-Exercised):** **0.15% on option premium** on the sell side.
   - **Option Exercise Settlement:** **0.15% on intrinsic settlement value** ($\max(0, S_{\text{spot}} - K) \times \text{Quantity}$) levied on the option buyer upon in-the-money contract expiration.
2. **Brokerage:** Discount broker standard of ₹20 flat per executed order (or 0.03%, whichever is lower).
3. **Goods & Services Tax (GST):** **18% applied strictly to the taxable service base**:
   $$\text{GST Base} = \text{Brokerage} + \text{Exchange Transaction Charges (including IPFT)} + \text{SEBI Turnover Fees}$$
   *(STT and Stamp Duty are sovereign taxes/levies and are strictly excluded from the GST base).*
4. **SEBI Turnover Charges:** ₹10 per crore of premium turnover (0.0001%).
5. **Stamp Duty:** 0.003% on buy-side premium turnover.

### C. Bid-Ask Spread Friction
At the money (ATM) NIFTY weekly options typically trade with a bid-ask spread of ₹0.50 to ₹2.00 per contract. On a ₹100 premium, crossing the spread on entry and exit imposes an immediate **1.0% to 2.0% capital drag**, establishing a formidable hurdle rate for high-frequency trading.

---

## 5. Contract Expiry Authority & Calendar Architecture

1. **Instrument Master Authority:**  
   The `expiry` column in the daily `kite_instruments_master.csv` is the **authoritative ground truth** for every derivative contract.
2. **Calendar Validation:**  
   Under current standard schedules, NIFTY weekly options expire on Tuesday, shifting to **the previous trading day if Tuesday is a holiday**. However, **weekday rules must never override the instrument master**. If the exchange issues an ad-hoc circular altering expiry dates, the date published in the broker instrument master is authoritative.

---

## 6. Conclusions & Research Mandates

### Canonical Specification Reference:
The full data contracts, feature schemas, strategy interfaces, execution models, and evaluation matrix are authoritatively specified in:  
👉 [`docs/research/fno/fno_core_engine_and_strategy_lab_spec.md`](file:///Users/shivamsingh/personal/nomad-analyst/docs/research/fno/fno_core_engine_and_strategy_lab_spec.md)

1. **Option Buying Hypotheses are Unproven:** Candidate strategies (ORB, VWAP Reclaim) are **unproven hypotheses** to evaluate prospectively, not established profitable systems.
2. **Prospective Capture Foundation:** Because historical expired option candles are not provided by Kite Connect, prospective high-fidelity live capture (1m OHLCV, Open Interest, Bid/Ask depth) is the only viable foundation for forward validation.
3. **Four-Pillar Architecture:** The system relies on (a) Shared Core Intelligence Engine emitting immutable feature snapshots, (b) Extensible Instrument Universe with NIFTY options as initial configuration boundary, (c) Independent Strategy Modules inheriting from `BaseStrategy`, and (d) Shared Paper-Trading Lab with independent ledgers and multi-metric anti-curve-fitting evaluation.
4. **One-Month Prospective Evaluation Lab (Phase 5):** Candidate strategies will be executed in parallel for 1 calendar month against live market data, evaluated using expectancy, friction drag ratios, profit factors, drawdowns, and statistical uncertainty ($t$-statistic). No strategy will be selected on total P&L alone.
