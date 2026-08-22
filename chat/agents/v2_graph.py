from typing import TypedDict, List, Dict, Any, Optional
import json
from django.utils import timezone
from langgraph.graph import StateGraph, START, END
from llm.gemini_api import GeminiAPIProvider
from llm.tools.registry import ToolRegistry
from chat.agents.planner import PlannerAgent
import logging

logger = logging.getLogger(__name__)

class AgentGraphState(TypedDict):
    """LangGraph execution state representing the current run status."""
    messages: List[Dict[str, Any]]
    plan: List[str]
    step_index: int
    scraped_data: str  # Accumulator for all gathered evidence/facts
    customized_resume_path: str
    screenshot_name: str
    human_approved: bool
    status: str
    user_profile_data: Dict[str, Any]
    agent_memories: List[str]
    prompt_tokens: int
    completion_tokens: int
    agent_run_id: Optional[int]
    research_run_id: Optional[str]  # Mapped to Postgres research run
    conversation_id: str
    retry_count: int
    error: Optional[str]


def stream_agent_update(conversation_id: str, event_type: str, data: dict):
    """Sends a real-time event update to the WebSocket channel layer group for the conversation."""
    if not conversation_id:
        return
    try:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            payload = {
                "type": "chat_message",
                "event_type": event_type,
                "data": data
            }
            
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Active event loop detected (e.g. async tests). Run via background task.
                loop.create_task(channel_layer.group_send(f"chat_{conversation_id}", payload))
            else:
                # Sync context (e.g. views, celery tasks). Run via async_to_sync.
                from asgiref.sync import async_to_sync
                async_to_sync(channel_layer.group_send)(f"chat_{conversation_id}", payload)
            
            logger.info(f"Streamed WebSocket event '{event_type}' to group chat_{conversation_id}")
    except Exception as e:
        logger.error(f"Failed to stream WebSocket event '{event_type}': {str(e)}")


def memory_injection_node(state: AgentGraphState) -> Dict[str, Any]:
    """Retrieves persistent memories for the user and injects them into the state."""
    username = state.get("user_profile_data", {}).get("username")
    if not username:
        return {"agent_memories": []}

    logger.info(f"Retrieving memories for user {username}...")
    from chat.models import AgentMemory
    memory_objs = AgentMemory.objects.filter(user_profile__username=username)
    
    agent_memories = []
    for m in memory_objs:
        agent_memories.append(f"{m.category}.{m.key}: {m.value}")
        
    logger.info(f"Retrieved memories: {agent_memories}")
    return {"agent_memories": agent_memories}


def planner_node(state: AgentGraphState) -> Dict[str, Any]:
    """Generates the execution plan if not already created."""
    if state.get("plan"):
        return {}

    last_user_message = ""
    for msg in reversed(state["messages"]):
        if msg["role"] == "user":
            last_user_message = msg["content"]
            break

    # Bypass planner for simple greetings/short queries
    clean_msg = last_user_message.strip().lower()
    is_greeting = clean_msg in ["hello", "hi", "hey", "test"] or (len(clean_msg) < 15 and not any(w in clean_msg for w in ["research", "stock", "price", "market", "sector", "company", "reliance", "tcs", "infy"]))
    
    if is_greeting:
        logger.info("Generic/short query detected. Bypassing planner...")
        plan = ["general_task"]
        stream_agent_update(state.get("conversation_id"), "planner_plan", {
            "plan": plan,
            "message": "Generic/short query detected. Bypassing planner..."
        })
        return {
            "plan": plan,
            "step_index": 0,
            "status": "Researching"
        }

    logger.info("Initializing high-level plan...")
    stream_agent_update(state.get("conversation_id"), "planner_start", {
        "message": "Initializing high-level plan..."
    })
    
    from chat.orchestrator.single_agent import SingleAgentOrchestrator
    orchestrator = SingleAgentOrchestrator()
    orchestrator.provider.set_active_conversation(state.get("conversation_id"))
    planner = PlannerAgent(provider=orchestrator.provider)

    plan = planner.generate_plan(last_user_message)
    if not plan:
        plan = ["research_financials", "research_moat", "research_valuation"]
    logger.info(f"Generated Plan: {plan}")

    # Create postgres ResearchRun record
    from research.models import ResearchRun
    research_run_id = None
    try:
        run = ResearchRun.objects.create(
            research_type="COMPANY_RESEARCH",
            query=last_user_message,
            status="running"
        )
        research_run_id = str(run.id)
        logger.info(f"Created ResearchRun record with ID: {research_run_id}")
    except Exception as run_err:
        logger.error(f"Failed to create ResearchRun: {run_err}")

    stream_agent_update(state.get("conversation_id"), "planner_plan", {
        "plan": plan,
        "message": f"Generated high-level plan with {len(plan)} steps."
    })

    return {
        "plan": plan,
        "step_index": 0,
        "status": "Researching",
        "research_run_id": research_run_id
    }


def executor_node(state: AgentGraphState) -> Dict[str, Any]:
    """Executes the current step in the plan using the ResearchAgent."""
    plan = state["plan"]
    step_index = state["step_index"]
    current_goal = plan[step_index]

    logger.info(f"Executing step {step_index + 1}/{len(plan)}: {current_goal}")

    from chat.orchestrator.single_agent import SingleAgentOrchestrator
    orchestrator = SingleAgentOrchestrator()
    orchestrator.provider.set_active_conversation(state.get("conversation_id"))
    provider = orchestrator.provider
    tool_registry = orchestrator.tool_registry

    from chat.agents.research_agent import ResearchAgent

    memory_context = ""
    if state.get("agent_memories"):
        memory_context = f"User preference profile & rules:\n" + "\n".join(state["agent_memories"]) + "\n\n"

    status = "Researching"
    
    stream_agent_update(state.get("conversation_id"), "executor_step_start", {
        "goal": current_goal,
        "status": status,
        "step_index": step_index
    })

    # Adapt prompts for stock research
    prompt = (
        f"{memory_context}"
        f"You are conducting investment research. Perform the specific sub-goal: {current_goal}.\n"
        "Leverage tools like get_stock_snapshot and search_web to look up price metrics and company news."
    )

    agent_run_id = state.get("agent_run_id")
    research_run_id = state.get("research_run_id")
    conversation_id = state.get("conversation_id")
    
    def log_tool_execution(tool_name: str, tool_args: dict, tool_result: str, status: str):
        if agent_run_id:
            from chat.models import ToolExecution, AgentRun
            run = AgentRun.objects.filter(id=agent_run_id).first()
            if run:
                ToolExecution.objects.create(
                    agent_run=run,
                    tool_name=tool_name,
                    input_data=tool_args,
                    output_data={"result": str(tool_result)[:10000]},
                    status=status
                )
        
        # Log evidence for reproducibility
        if research_run_id:
            try:
                from research.models import Evidence
                Evidence.objects.create(
                    research_run_id=research_run_id,
                    source_type="api" if tool_name == "get_stock_snapshot" else "web",
                    source_name=tool_name,
                    source_url=tool_args.get("url") or tool_args.get("file_path"),
                    title=f"Tool Execution: {tool_name}",
                    content=str(tool_result),
                    metadata={"arguments": tool_args, "status": status}
                )
                logger.info(f"Recorded research evidence for tool: {tool_name}")
            except Exception as ev_err:
                logger.error(f"Failed to save evidence: {ev_err}")

        # Stream tool execution to WebSockets
        stream_agent_update(conversation_id, "tool_execution", {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": str(tool_result)[:1000],
            "status": status
        })

    try:
        agent = ResearchAgent(provider=provider, tool_registry=tool_registry)
        response_text = agent.execute(prompt=prompt, on_tool_execution=log_tool_execution)
        
        # Accumulate research evidence
        existing_data = state.get("scraped_data", "") or ""
        accumulated_evidence = existing_data + f"\n\n### Findings for goal '{current_goal}':\n{response_text}\n"

        updates = {
            "step_index": step_index + 1,
            "status": status,
            "messages": state["messages"] + [{"role": "assistant", "content": f"Completed goal '{current_goal}': {response_text}"}],
            "prompt_tokens": state.get("prompt_tokens", 0) + getattr(agent, "accumulated_prompt_tokens", 0),
            "completion_tokens": state.get("completion_tokens", 0) + getattr(agent, "accumulated_completion_tokens", 0),
            "scraped_data": accumulated_evidence
        }

        stream_agent_update(conversation_id, "executor_step_end", {
            "goal": current_goal,
            "response": response_text,
            "status": status
        })

        return updates

    except BaseException as e:
        logger.error(f"Error executing step {current_goal}: {str(e)}", exc_info=True)
        stream_agent_update(conversation_id, "executor_step_failed", {
            "goal": current_goal,
            "error": str(e)
        })
        return {
            "error": str(e),
            "status": "Failed"
        }


def critic_node(state: AgentGraphState) -> Dict[str, Any]:
    """Evaluates the latest executed plan step. Triggering retries if deficient."""
    if state.get("error"):
        return {}

    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)
    
    # The step that just finished is at step_index - 1
    completed_idx = step_index - 1
    if completed_idx < 0 or completed_idx >= len(plan):
        return {}

    current_goal = plan[completed_idx]
    
    # Bypass critic for simple/fallback tasks
    if current_goal == "general_task":
        return {}

    # Extract latest assistant message content
    latest_response = ""
    for m in reversed(state.get("messages", [])):
        if m.get("role") == "assistant" and f"Completed goal '{current_goal}'" in (m.get("content") or ""):
            latest_response = m.get("content")
            break

    if not latest_response:
        return {}

    conversation_id = state.get("conversation_id")
    logger.info(f"Running reflection critic for step: {current_goal}...")
    stream_agent_update(conversation_id, "critic_start", {
        "message": f"Critiquing output for step '{current_goal}'..."
    })

    from chat.orchestrator.single_agent import SingleAgentOrchestrator
    orchestrator = SingleAgentOrchestrator()
    orchestrator.provider.set_active_conversation(conversation_id)
    provider = orchestrator.provider

    prompt = (
        f"You are a strict quality controller. Evaluate if the following step execution was successful.\n\n"
        f"Step Name: {current_goal}\n"
        f"Execution Output: {latest_response}\n\n"
        f"Check for common errors:\n"
        f"- Empty content or placeholder text\n"
        f"- Out of memory or missing file errors\n"
        f"- Failure to complete the core action\n\n"
        f"Provide a brief critique detailing any deficiencies. Return ONLY a JSON object matching:\n"
        f"{{\n"
        f"  \"success\": true/false,\n"
        f"  \"critique\": \"Reason for failure or confirmation of success\"\n"
        f"}}"
    )

    system_prompt = "You are a quality controller. Respond ONLY with valid JSON containing 'success' and 'critique' keys."

    try:
        response = provider.generate(prompt=prompt, system_prompt=system_prompt, tools=None)
        text = response.get("text", "")

        # Clean code wraps
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text.strip())
        success = data.get("success", True)
        critique = data.get("critique", "")
    except Exception as e:
        logger.error(f"Failed to run quality control critic: {e}")
        success = True
        critique = "Fallback pass due to system error."

    retry_count = state.get("retry_count", 0)
    if success or retry_count >= 2:
        if not success:
            logger.warning(f"Step {current_goal} failed critic but reached max retries. Proceeding.")
            stream_agent_update(conversation_id, "critic_max_retries", {
                "message": f"Step '{current_goal}' failed critique but reached max retries. Proceeding.",
                "critique": critique
            })
        else:
            logger.info(f"Step {current_goal} passed critic.")
            stream_agent_update(conversation_id, "critic_pass", {
                "message": f"Step '{current_goal}' passed critique.",
                "critique": critique
            })
        
        # Reset retry count for next steps
        return {
            "retry_count": 0
        }
    else:
        # Critic failed and retries remain. Trigger execution node retry!
        logger.warning(f"Step {current_goal} failed critic. Retrying step. Critique: {critique}")
        stream_agent_update(conversation_id, "critic_fail", {
            "message": f"Step '{current_goal}' failed critique. Retrying step...",
            "critique": critique,
            "retry_count": retry_count + 1
        })

        feedback_msg = {
            "role": "user",
            "content": f"CRITIQUE FOR STEP '{current_goal}': {critique}. Please execute the step again and address these points."
        }

        return {
            "step_index": completed_idx,  # Reset step index back
            "messages": state["messages"] + [feedback_msg],
            "retry_count": retry_count + 1
        }


def route_after_critic(state: AgentGraphState):
    """Determines transition path after critic node completes verification."""
    if state.get("error"):
        return "memory_extraction"

    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)

    if step_index >= len(plan):
        return "memory_extraction"

    return "executor"


def memory_extraction_node(state: AgentGraphState) -> Dict[str, Any]:
    """Analyzes message log, extracts long-term memories, and synthesizes final ResearchReport."""
    username = state.get("user_profile_data", {}).get("username")
    conversation_id = state.get("conversation_id")
    research_run_id = state.get("research_run_id")
    scraped_data = state.get("scraped_data", "")

    from chat.orchestrator.single_agent import SingleAgentOrchestrator
    orchestrator = SingleAgentOrchestrator()
    orchestrator.provider.set_active_conversation(conversation_id)
    provider = orchestrator.provider

    # 1. Synthesize final report and mark ResearchRun complete
    if research_run_id and scraped_data:
        try:
            logger.info("Synthesizing final stock market investment research report...")
            from llm.prompts import PromptRegistry
            from research.models import ResearchReport, ResearchRun
            
            run_obj = ResearchRun.objects.filter(id=research_run_id).first()
            query_str = run_obj.query if run_obj else "Stock Market Research"
            
            rendered_sys = PromptRegistry.render(
                key="market.evidence_synthesizer.system",
                variables={}
            )
            system_prompt = rendered_sys["rendered_prompt"]
            
            rendered_user = PromptRegistry.render(
                key="market.evidence_synthesizer.user",
                variables={
                    "target_name": query_str,
                    "evidence_list": scraped_data
                }
            )
            user_prompt = rendered_user["rendered_prompt"]
            
            # Generate the report
            report_response = provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                tools=None
            )
            report_text = report_response.get("text", "")
            
            # Create report record
            ResearchReport.objects.create(
                research_run_id=research_run_id,
                title=f"Investment Research Report: {query_str[:100]}",
                summary=f"Synthesized report for query: {query_str}",
                analysis=report_text
            )
            
            # Mark complete
            ResearchRun.objects.filter(id=research_run_id).update(
                status="completed",
                completed_at=timezone.now()
            )
            logger.info("Successfully saved synthesized ResearchReport and marked run complete!")
            
            stream_agent_update(conversation_id, "report_synthesized", {
                "message": "Final investment research report synthesized successfully!",
                "report_title": f"Investment Research Report: {query_str[:100]}",
                "analysis": report_text
            })
            
        except Exception as report_err:
            logger.error(f"Error generating final report: {report_err}", exc_info=True)
            if research_run_id:
                from research.models import ResearchRun
                ResearchRun.objects.filter(id=research_run_id).update(status="failed")

    # 2. Extract long-term user memories/preferences
    if username and state.get("plan") != ["general_task"]:
        logger.info(f"Running memory extraction for user {username}...")
        chat_log = []
        for m in state.get("messages", []):
            chat_log.append(f"{m.get('role')}: {m.get('content') or ''}")
            
        prompt = (
            "Analyze the following conversation logs. Extract any user preferences, experience profile details, or specific rules.\n"
            "Return a JSON object containing a list of objects under 'memories'. Each object must have:\n"
            "- 'category': String (e.g., 'preference', 'profile', 'experience')\n"
            "- 'key': String (e.g., 'blocked_companies', 'tech_stack', 'work_location')\n"
            "- 'value': JSON array or object containing the facts.\n\n"
            f"Conversation Logs:\n" + "\n".join(chat_log)
        )
        
        system_prompt = (
            "You are an assistant that extracts user preferences and profile facts to build a long-term memory. "
            "Return only JSON matching the schema: {\"memories\": [{\"category\": \"...\", \"key\": \"...\", \"value\": ...}]}"
        )

        try:
            response = provider.generate(prompt=prompt, system_prompt=system_prompt, tools=None)
            text = response.get("text", "")
            
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text.strip())
            memories = data.get("memories", [])
            
            from chat.models import UserProfile, AgentMemory
            user_profile = UserProfile.objects.get(username=username)
            
            for m in memories:
                category = m.get("category", "").lower()
                key = m.get("key", "").lower()
                value = m.get("value")
                
                if category and key and value is not None:
                    AgentMemory.objects.update_or_create(
                        user_profile=user_profile,
                        category=category,
                        key=key,
                        defaults={"value": value}
                    )
                    logger.info(f"Stored memory: {category}.{key} = {value}")
        except Exception as e:
            logger.error(f"Error extracting memories: {str(e)}")

    stream_agent_update(conversation_id, "run_completed", {
        "status": "Complete",
        "message": "Agent execution completed successfully!"
    })
    return {}


def get_v2_agent_graph(checkpoint_saver=None):
    """Compiles the V2 agent execution graph workflow."""
    workflow = StateGraph(AgentGraphState)

    # Register nodes
    workflow.add_node("memory_injection", memory_injection_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("memory_extraction", memory_extraction_node)

    # Register edges
    workflow.add_edge(START, "memory_injection")
    workflow.add_edge("memory_injection", "planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "critic")
    
    # Register conditional edges
    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "executor": "executor",
            "memory_extraction": "memory_extraction"
        }
    )

    workflow.add_edge("memory_extraction", END)

    return workflow.compile(checkpointer=checkpoint_saver)
