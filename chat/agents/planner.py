import json
import logging
from llm.gemini_api import GeminiAPIProvider
from llm.prompts import PromptRegistry

logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    High-level Planner Agent responsible for breaking down a stock or sector research query
    into a sequence of structured goals (a plan) using the bootstrapped prompts.
    """
    def __init__(self, provider: GeminiAPIProvider):
        self.provider = provider

    def generate_plan(self, prompt: str) -> list[str]:
        try:
            rendered_sys = PromptRegistry.render(
                key="market.research_planner.system",
                variables={}
            )
            system_prompt = rendered_sys["rendered_prompt"]
            
            rendered_user = PromptRegistry.render(
                key="market.research_planner.user",
                variables={
                    "target_name": prompt,
                    "sector": "Indian Stock Market",
                    "extra_instructions": ""
                }
            )
            user_prompt = rendered_user["rendered_prompt"]
        except Exception as e:
            logger.error(f"Failed to load planner prompts: {e}. Falling back to default.")
            system_prompt = (
                "You are a senior investment research planner. Your task is to break down a stock or sector research target into a list of specific research goals.\n"
                "Return a JSON object containing a list of strings under the 'plan' key. Example:\n"
                "{\"plan\": [\"research_financials\", \"research_moat\", \"research_valuation\"]}"
            )
            user_prompt = f"Target: {prompt}"

        response = self.provider.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            tools=None
        )

        text = response.get("text", "")
        try:
            # Clean code block backticks if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(text.strip())
            # Handle if AI returned a list directly or an object with 'plan'
            if isinstance(data, list):
                return data
            return data.get("plan", [])
        except Exception as e:
            logger.error(f"Error parsing planner response: {str(e)}. Raw text: {text}")
            # Semantic fallback: use standard research steps
            return ["research_financials", "research_moat", "research_valuation"]
