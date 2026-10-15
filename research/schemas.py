from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class StructuredResearchOutput(BaseModel):
    """
    Normalized, structured research report schema adhering to Phase 17E.
    Must separate observed facts from analyst interpretation, articulate
    contradictions, unknowns, and invalidation criteria without issuing trade orders.
    """
    summary: str = Field(
        description="Concise executive synthesis outlining key findings from the deterministic evidence package."
    )
    observed_facts: List[str] = Field(
        default_factory=list,
        description="Strictly verified empirical facts derived directly from the provided evidence (prices, ratios, indicators)."
    )
    analyst_interpretation: str = Field(
        description="Reasoned synthesis explaining the dynamics, momentum, structure, or fundamental drivers connecting the facts."
    )
    why_interesting: List[str] = Field(
        default_factory=list,
        description="Key catalysts, structural setups, or divergences that make this asset noteworthy."
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Specific pieces of evidence that support a constructive thesis."
    )
    contradicting_evidence: List[str] = Field(
        default_factory=list,
        description="Conflicting signals, divergent breadth, weakening momentum, or data that opposes the thesis."
    )
    key_risks: List[str] = Field(
        default_factory=list,
        description="Primary contextual, market, liquidity, or fundamental risks."
    )
    unknowns: List[str] = Field(
        default_factory=list,
        description="Explicit gaps in available data (e.g. missing management commentary, stale indicators)."
    )
    market_context_interpretation: str = Field(
        default="",
        description="Interpretation of how the broader market regime, direction, and breadth impact this opportunity."
    )
    sector_context_interpretation: str = Field(
        default="",
        description="Interpretation of sector rotation, relative strength, and peer momentum."
    )
    thesis: str = Field(
        description="Central analytical thesis explaining the opportunity or condition."
    )
    thesis_strength: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        default="MEDIUM",
        description="Strength of the thesis given supporting vs contradicting factors."
    )
    what_to_monitor: List[str] = Field(
        default_factory=list,
        description="Key upcoming levels, data releases, volume developments, or breadth indicators to watch next."
    )
    invalidating_developments: List[str] = Field(
        default_factory=list,
        description="Specific conditions or price/market actions that would invalidate this thesis."
    )
    research_confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        default="MEDIUM",
        description="Confidence level in the research findings based on evidence coverage and freshness."
    )

    from pydantic import model_validator

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, values):
        if isinstance(values, dict):
            # If summary is missing but thesis or other summary exists
            if not values.get("summary"):
                values["summary"] = values.get("thesis") or values.get("executive_summary") or values.get("asset_identification", "") or "Intraday opportunity analysis synthesized from evidence package."
            if not values.get("thesis"):
                values["thesis"] = values.get("summary") or "Analytical thesis synthesized from quantitative evidence package."
            # If observed_facts is dict, flatten to list of strings
            if isinstance(values.get("observed_facts"), dict):
                flattened = []
                for k, v in values["observed_facts"].items():
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            flattened.append(f"{sub_k}: {sub_v}")
                    else:
                        flattened.append(f"{k}: {v}")
                values["observed_facts"] = flattened
            elif isinstance(values.get("observed_facts"), str):
                values["observed_facts"] = [values["observed_facts"]]
            # If analyst_interpretation is dict, flatten to string
            if isinstance(values.get("analyst_interpretation"), dict):
                values["analyst_interpretation"] = "\n".join(f"{k}: {v}" for k, v in values["analyst_interpretation"].items())
        return values
