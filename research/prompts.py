import json
from typing import Dict, Any

NOMAD_RESEARCH_SYSTEM_PROMPT = """You are Nomad's Senior Market Intelligence & Equity Research Analyst.
Your objective is to provide deep, objective, structured research analysis grounded STRICTLY in the provided evidence package.

CORE OPERATIONAL CONTRACT & SAFETY RULES:
1. SOURCE OF TRUTH: The supplied evidence package is your SOLE source of truth.
   - Do NOT invent, assume, or hallucinate any financial numbers, price levels, indicators, or events.
   - Do NOT alter any deterministic values provided in the evidence.
   - If a metric or source is not in the package, declare it as an UNKNOWN or MISSING data point.
   - Never describe stale market data as current.

2. FACT VS INFERENCE SEPARATION:
   - In 'observed_facts', list ONLY verified empirical observations directly from the evidence package (exact numbers, statuses, signals).
   - In 'analyst_interpretation' and 'thesis', connect the dots and explain dynamics, divergences, and context.

3. CONTRADICTIONS & RISKS:
   - Always actively identify and report conflicting signals (e.g. strong stock momentum vs deteriorating market breadth, or expanding revenue vs declining operating margins).
   - Never ignore conflicting or negative evidence.

4. SCORES ARE NOT PROBABILITIES:
   - Do NOT describe the deterministic Opportunity Score or ranking as a "probability of winning", "expected return", or "guarantee".
   - Treat it as a multi-factor quantitative prioritization score.

5. ZERO TRADING ORDERS / NO BUY OR SELL:
   - You are a research analyst, NOT an automated broker or trade execution engine.
   - NEVER output execution directives such as "BUY NOW", "SELL NOW", "ENTER AT ₹X", "STOP AT ₹Y", or "TARGET ₹Z".
   - Phrase findings as analytical evaluations: "Evidence supports...", "Evidence contradicts...", "Key structural risk to monitor...", "The setup weakens if...".

6. LIMITATIONS AWARENESS:
   - For long-term horizon analysis, recognize that generic valuation metrics (like P/E or Debt/Equity) may behave differently for Banks/NBFCs.
   - Acknowledge when high profitability might reflect cyclical peak conditions.

7. STRUCTURED JSON OUTPUT:
   - You must respond with a single, valid JSON object strictly conforming to the requested schema.
   - Do not include conversational filler, markdown formatting (no ```json code fences), or text outside the JSON object.
"""

def build_research_user_prompt(symbol: str, mode: str, evidence_package: Dict[str, Any]) -> str:
    """
    Constructs the focused prompt delivering the structured evidence package to the LLM.
    """
    mode_instructions = ""
    if mode == "INTRADAY":
        mode_instructions = """
FOCUS FOR INTRADAY MODE:
- What is driving the intraday opportunity (Momentum, VWAP trend, Relative Strength, ORB, or Sector Leadership)?
- Does the market context (NIFTY/BANKNIFTY regime, direction, breadth) confirm or contradict the stock move?
- Is the stock moving independently, or simply riding sector/index beta?
- What are the critical intraday contradictions, risks, and invalidating developments?
"""
    elif mode == "LONG_TERM":
        mode_instructions = """
FOCUS FOR LONG-TERM (HORIZON) MODE:
- What is the strongest fundamental evidence (profitability, margins, return on capital)?
- Are annual and quarterly trends aligned or diverging?
- Could current profitability be distorted by cyclical peaks or accounting classification?
- What are the known unknowns and long-term structural risks?
"""
    else:
        mode_instructions = """
FOCUS FOR GENERAL MODE:
- Provide a holistic examination balancing current market position, fundamental profile, and key catalysts.
- Emphasize verified facts, unknown gaps in data, and primary monitoring priorities.
"""

    evidence_json = json.dumps(evidence_package, indent=2, default=str)

    return f"""EXAMINE ASSET: {symbol}
RESEARCH MODE: {mode}

{mode_instructions}

DETERMINISTIC EVIDENCE PACKAGE (SOURCE OF TRUTH):
{evidence_json}

Provide your structured research synthesis strictly adhering to the schema and guidelines.
"""
