# src/cmp_copilot/agents/supervisor.py

import logging
import json
import asyncio
from typing import Dict

# --- CORRECTED IMPORTS ---
# Use relative imports to correctly locate modules within the same package.
from .state import AgentState
from ..core.llm import get_llm_client
from ..prompts.system_prompts import SUPERVISOR_PROMPT

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def supervisor_node(state: AgentState) -> Dict:
    """
    The first node in the agent's workflow. It parses the user's query
    and creates a structured plan for execution.

    Args:
        state (AgentState): The current state of the agent's memory.

    Returns:
        Dict: A dictionary containing the updates to be made to the state.
    """
    logging.info("--- SUPERVISOR NODE ---")
    
    # Announce the action for the streaming UI
    initial_message = "Parsing user query to create a plan..."
    state['messages'].append(("system", initial_message))

    llm = get_llm_client()
    
    user_query = state['user_query']
    formatted_prompt = SUPERVISOR_PROMPT.format(user_query=user_query)
    
    messages_for_llm = [
        {"role": "user", "content": formatted_prompt}
    ]

    try:
        logging.info("Invoking LLM to generate a plan...")
        response_str = await llm.invoke_chat_completion(messages_for_llm, json_mode=True)
        
        if not response_str:
            logging.error("LLM returned an empty response for the plan.")
            return {"error_log": ["Supervisor: LLM returned an empty plan."]}

        plan = json.loads(response_str)
        logging.info(f"Successfully parsed plan from LLM: {plan}")
        
        plan_created_message = f"Plan created successfully. Action: '{plan.get('action', 'N/A')}'."
        state['messages'].append(("system", plan_created_message))

        return {"plan": plan}

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from LLM response: {response_str}. Error: {e}")
        error_message = "Supervisor: Failed to understand the plan from the AI. Please try rephrasing your query."
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}
        
    except Exception as e:
        logging.error(f"An unexpected error occurred in the supervisor node: {e}", exc_info=True)
        error_message = f"Supervisor: An unexpected error occurred: {e}"
        state['messages'].append(("system", error_message))
        return {"error_log": [error_message]}
