import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import Counter

from .base import BaseAgent
from llm.tools.registry import ToolRegistry
from llm.tools.executor import ToolExecutor
from llm.tools.context import ToolContext
from market.models import Company, Instrument

logger = logging.getLogger(__name__)

class ResearchLoopState:
    """Tracks the history of tool calls within a single execution loop to detect stuck loops."""
    def __init__(self):
        self.tool_history: List[tuple[str, str]] = []
        self.error_streak = 0
        
    def record_tool_call(self, tool_name: str, tool_args: dict, success: bool):
        key_parts = []
        for k in ("symbol", "timeframe", "name", "event_type"):
            if k in tool_args:
                key_parts.append(f"{k}={tool_args[k]}")
        key_str = ",".join(key_parts) if key_parts else str(tool_args)
        self.tool_history.append((tool_name, key_str))
        
        if success:
            self.error_streak = 0
        else:
            self.error_streak += 1
            
    def is_stuck(self) -> bool:
        if len(self.tool_history) < 3:
            return False
        # If the same tool and arguments are called 3+ times in the last 5 calls
        recent = self.tool_history[-5:]
        counts = Counter(recent)
        for (tool_name, key_str), count in counts.items():
            if count >= 3:
                return True
        return False


class MarketResearchAgent(BaseAgent):
    """
    Agent responsible for conducting structured stock research.
    Combines quantitative features, fundamental data, news headlines,
    enforcing strict PIT safety, conflict resolution, and evidence provenance.
    """

    @property
    def name(self) -> str:
        return "MarketResearchAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a professional equity research assistant investigating Indian stock market assets. "
            "Your objective is to compile an objective, structured, fact-grounded intelligence report.\n\n"
            
            "CRITICAL OPERATIONAL RULES:\n"
            "1. TOOL-FIRST: You must use tools to retrieve all market, fundamental, news, and technical facts. "
            "NEVER invent or hallucinate dates, financial numbers, or price figures.\n"
            "2. PIT SAFETY: If an 'as_of' date is specified in the prompt/metadata, you must not use or reveal any information "
            "published or occurring after that timestamp. All tool calls you make must respect this date.\n"
            "3. NO RECOMMENDATIONS: You must NOT provide BUY, SELL, or HOLD ratings, target prices, or trade advice UNLESS you "
            "have retrieved them via 'get_recommendations', 'get_recommendation', or 'get_active_recommendations' tools. "
            "You MUST NOT invent, calculate, or modify any entry_price, stop_price, target_price, or signal values.\n"
            "4. EVIDENCE: Every fact in your final report must be traced to a specific tool output (source URL, statement period, or date).\n"
            "5. NO FINANCIAL CERTAINTY: Highlight uncertainties, contradictions, and insufficient data. If data is missing, output 'Insufficient data' instead of fabricating numbers.\n"
            "6. OPPORTUNITY DISCOVERY: If asked to scan for stock opportunities, analyze sectors, or discover candidates, you MUST use 'get_stock_opportunities', 'get_stock_opportunity', or 'get_sector_opportunities'. Report the scores, types, pros, and risks EXACTLY as returned by the tools. You MUST NOT calculate scores yourself or modify scores returned by the tools.\n"
            "7. RECOMMENDATIONS: If asked about actionable recommendations, signals, or trade setups:\n"
            "   - Use 'get_active_recommendations' for a broad view of open setups.\n"
            "   - Use 'get_recommendations' to filter by horizon, signal, or ticker.\n"
            "   - Use 'get_recommendation' for full detail on a specific setup.\n"
            "   - NEVER alter, recalculate, or override the entry_price, stop_price, target_price, signal, or confidence returned by these tools.\n"
            "   - You MAY explain WHY the deterministic system generated the recommendation (using the supporting_factors, risk_factors, and setup_details returned), "
            "but you MUST clearly attribute all numeric values to the tool output, not your own reasoning.\n"
            "   - If a recommendation has 'INSUFFICIENT_DATA' or 'NOT_READY' as its signal, you MUST NOT attempt to substitute your own direction.\n"
            "8. OUTPUT CONTRACT: Your final response MUST be a single JSON object matching the ResearchReport schema:\n"
            "{\n"
            "  \"company\": \"Company Name\",\n"
            "  \"instrument\": \"SYMBOL\",\n"
            "  \"as_of\": \"ISO string or null\",\n"
            "  \"summary\": \"Executive Summary paragraph\",\n"
            "  \"market_snapshot\": { ... },\n"
            "  \"technical_analysis\": \"Technicals findings, indicators, trends\",\n"
            "  \"fundamental_analysis\": \"Margins, statements trends, leverage ratios\",\n"
            "  \"news_analysis\": \"Material news impact summary\",\n"
            "  \"positive_factors\": [\"list of positive indicators/facts\"],\n"
            "  \"risks\": [\"list of clear risk factors/facts\"],\n"
            "  \"contradictions\": [\"list of conflicting signals (e.g. rising revenues but dropping margins)\"],\n"
            "  \"unknowns\": [\"missing or unconfirmed information\"],\n"
            "  \"evidence\": [\"traces linking statements back to specific period/source/tool output\"],\n"
            "  \"generated_at\": \"ISO timestamp\"\n"
            "}\n"
            "Do NOT include conversational chatter outside this JSON object."
        )

    def execute(self, prompt: str, conversation_history: list = None, **kwargs) -> str:
        on_tool_execution = kwargs.get("on_tool_execution")
        as_of = kwargs.get("as_of")  # Optional PIT string
        depth = kwargs.get("depth", "standard").upper()  # QUICK, STANDARD, DEEP
        
        tools_schema = self.tool_registry.get_tool_schemas() if self.tool_registry else None
        
        # Build prompt containing specific research constraints
        injected_prompt = (
            f"RESEARCH REQUEST:\n{prompt}\n\n"
            f"CONSTRAINTS:\n"
            f"- TARGET DATE (as_of): {as_of if as_of else 'CURRENT'}\n"
            f"- DEPTH: {depth}\n"
            f"Please run the required tools to fulfill this request. Output your final report in the requested JSON structure."
        )
        
        messages = [{"role": "user", "content": injected_prompt}]
        loop_state = ResearchLoopState()
        
        executor = ToolExecutor(self.tool_registry)
        agent_run_id = kwargs.get("agent_run_id")
        context = ToolContext(
            source="agent",
            agent_name=self.name,
            metadata={"agent_run_id": agent_run_id} if agent_run_id else {}
        )
        
        self.accumulated_prompt_tokens = 0
        self.accumulated_completion_tokens = 0
        
        max_iterations = 12 if depth == "DEEP" else (6 if depth == "QUICK" else 9)
        
        try:
            for iteration in range(max_iterations):
                # Build context messages
                prompt_parts = []
                if conversation_history:
                    prompt_parts.append("Conversation History:")
                    for msg in conversation_history:
                        prompt_parts.append(f"{msg['role']}: {msg['content']}")
                    prompt_parts.append("")
                    
                for msg in messages:
                    if msg["role"] == "user":
                        prompt_parts.append(f"User: {msg['content']}")
                    elif msg["role"] == "assistant":
                        content = msg.get("content") or ""
                        if msg.get("tool_call"):
                            content += f"\nCalling tool: {msg['tool_call']['name']} with {msg['tool_call']['args']}"
                        prompt_parts.append(f"Assistant: {content}")
                    elif msg["role"] == "tool":
                        prompt_parts.append(f"Tool '{msg.get('tool_name')}' returned:\n{msg['content']}")
                        
                current_prompt = "\n".join(prompt_parts)
                
                # Call router/Gemini
                result = self.provider.generate(
                    prompt=current_prompt,
                    system_prompt=self.system_prompt,
                    tools=tools_schema
                )
                
                self.accumulated_prompt_tokens += result.get("prompt_tokens", 0)
                self.accumulated_completion_tokens += result.get("completion_tokens", 0)
                
                if result.get("type") == "tool_call":
                    tool_name = result["tool_name"]
                    tool_args = result.get("tool_args", {})
                    
                    # Force PIT as_of alignment on the tool arguments at the agent execution level
                    if as_of:
                        tool_args["as_of"] = as_of
                        
                    messages.append({
                        "role": "assistant",
                        "content": result.get("text", ""),
                        "tool_call": {"name": tool_name, "args": tool_args}
                    })
                    
                    loop_state.record_tool_call(tool_name, tool_args, success=True)
                    if loop_state.is_stuck():
                        intervention = (
                            "STUCK DETECTED: You are calling the same tool repeatedly. "
                            "Please synthesize the final report using the data you already have, or output 'Insufficient data'."
                        )
                        messages.append({"role": "user", "content": intervention})
                        continue
                        
                    try:
                        exec_result = executor.execute(tool_name, tool_args, context=context)
                        
                        if exec_result.success:
                            tool_result = str(exec_result.data)
                            status = "success"
                        else:
                            tool_result = f"Error: {exec_result.error.message if exec_result.error else 'Unknown error'}"
                            status = "error"
                            
                        if on_tool_execution:
                            on_tool_execution(tool_name, tool_args, tool_result, status)
                            
                        messages.append({
                            "role": "tool",
                            "tool_name": tool_name,
                            "content": tool_result
                        })
                    except Exception as e:
                        tool_result = f"Tool execution failed: {str(e)}"
                        if on_tool_execution:
                            on_tool_execution(tool_name, tool_args, tool_result, "error")
                        messages.append({
                            "role": "tool",
                            "tool_name": tool_name,
                            "content": tool_result
                        })
                else:
                    return result.get("text", str(result))
                    
            # Fallback report if loop reached limit
            fallback_report = {
                "company": "Unknown",
                "instrument": "Unknown",
                "as_of": as_of,
                "summary": "Report generation exceeded maximum iteration steps. Partial research completed.",
                "market_snapshot": {},
                "technical_analysis": "Timeout/Limit reached during indicator retrieval.",
                "fundamental_analysis": "Timeout/Limit reached during statement parsing.",
                "news_analysis": "Timeout/Limit reached.",
                "positive_factors": [],
                "risks": ["Research process limit reached"],
                "contradictions": [],
                "unknowns": ["Incomplete execution loop"],
                "evidence": [],
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            return json.dumps(fallback_report)
            
        except Exception as e:
            logger.error(f"MarketResearchAgent error: {str(e)}")
            error_report = {
                "company": "Error",
                "instrument": "Error",
                "as_of": as_of,
                "summary": f"Failed to execute research due to system error: {str(e)}",
                "market_snapshot": {},
                "technical_analysis": "Unavailable",
                "fundamental_analysis": "Unavailable",
                "news_analysis": "Unavailable",
                "positive_factors": [],
                "risks": [f"System error: {str(e)}"],
                "contradictions": [],
                "unknowns": ["System failure details"],
                "evidence": [],
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            return json.dumps(error_report)
