import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from market.models import Company, Instrument
from chat.agents.market_research_agent import MarketResearchAgent
from llm.router import IntelligentRouter
from llm.tools.registry import ToolRegistry

from llm.tools.implementations.market_tool import (
    GetStockSnapshotTool,
    GetHistoricalOHLCVTool,
    GetTechnicalFeaturesTool,
    GetCompanyFinancialsTool,
    GetFinancialMetricsTool,
    GetCompanyNewsTool,
    GetCompanyEventsTool,
    GetMarketNewsTool
)

logger = logging.getLogger(__name__)

class MarketResearchService:
    """
    Exposes clean service interface to trigger stock research reports using the
    PIT-safe MarketResearchAgent and deterministic tools.
    """

    def __init__(self, provider=None):
        self.provider = provider or IntelligentRouter()
        self.tool_registry = ToolRegistry()
        
        # Register core deterministic tools
        self.tool_registry.register(GetStockSnapshotTool())
        self.tool_registry.register(GetHistoricalOHLCVTool())
        self.tool_registry.register(GetTechnicalFeaturesTool())
        self.tool_registry.register(GetCompanyFinancialsTool())
        self.tool_registry.register(GetFinancialMetricsTool())
        self.tool_registry.register(GetCompanyNewsTool())
        self.tool_registry.register(GetCompanyEventsTool())
        self.tool_registry.register(GetMarketNewsTool())
        
        self.agent = MarketResearchAgent(
            provider=self.provider,
            tool_registry=self.tool_registry
        )

    def research_stock(self, symbol: str, question: str, as_of: Optional[str] = None, depth: str = "standard") -> Dict[str, Any]:
        """
        Executes a research task using MarketResearchAgent.
        Returns a structured dictionary matching the report schema.
        """
        clean_symbol = symbol.strip().upper().split('.')[0]
        logger.info(f"Triggering research for {clean_symbol} (as_of={as_of}, depth={depth})")
        
        # Resolve company
        try:
            company = Company.objects.get(short_name=clean_symbol)
            company_name = company.name
        except Company.DoesNotExist:
            company_name = clean_symbol
            
        prompt = (
            f"Investigate company: {company_name} ({clean_symbol}).\n"
            f"Question: {question}"
        )
        
        # Execute agent
        result_raw = self.agent.execute(
            prompt=prompt,
            as_of=as_of,
            depth=depth
        )
        
        try:
            parsed = json.loads(result_raw)
            return parsed
        except json.JSONDecodeError:
            # Handle fallback parsing gracefully
            logger.warning("Agent did not return a valid JSON object. Wrapping raw text response.")
            return {
                "company": company_name,
                "instrument": clean_symbol,
                "as_of": as_of,
                "summary": result_raw,
                "market_snapshot": {},
                "technical_analysis": "Failed to parse JSON schema output from agent.",
                "fundamental_analysis": "Failed to parse JSON schema output.",
                "news_analysis": "Unavailable",
                "positive_factors": [],
                "risks": ["Malformed LLM response formatting"],
                "contradictions": [],
                "unknowns": ["Response parsing error"],
                "evidence": [],
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
