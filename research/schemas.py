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
