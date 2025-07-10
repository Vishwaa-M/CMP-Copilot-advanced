# src/cmp_copilot/app/main.py

import logging
import json
import uvicorn
from typing import List, Dict

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- CORRECTED IMPORT ---
from ..core.agent import create_agent_graph

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
app = FastAPI(
    title="CMP Copilot Agent",
    description="An agentic AI for cloud management and security scanning.",
    version="1.2.0" # Version bump for the final fix
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_graph = create_agent_graph()

# --- Pydantic Models for Request Body ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str

# --- FINAL ROBUST STREAMING LOGIC ---
async def stream_agent_response(user_query: str):
    """
    This async generator function calls the agent and yields formatted
    chunks for the Open Web UI. It now robustly captures the final state.
    """
    logger.info(f"Starting agent stream for query: '{user_query}'")
    
    inputs = {"user_query": user_query}
    
    # This dictionary will aggregate the outputs from all nodes.
    final_state = {}

    try:
        # Stream the agent's execution steps
        async for event in agent_graph.astream(inputs):
            # The event is a dictionary where keys are the node names
            for node_name, node_output in event.items():
                
                # --- FIX: Manually update our copy of the final state ---
                # This ensures we capture the output of EVERY node.
                if node_output:
                    final_state.update(node_output)

                # Check for and stream intermediate messages
                if "messages" in node_output:
                    for role, content in node_output["messages"]:
                        chunk = {
                            "choices": [{"delta": {"role": "assistant", "content": content + "\n\n"}}]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
        
        # After the stream is complete, process the aggregated final state
        summary = final_state.get("final_summary", "Agent execution finished, but no summary was produced.")
        
        # Send the final summary as the last piece of content
        final_chunk = {
            "choices": [{"delta": {"role": "assistant", "content": summary}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"

    except Exception as e:
        logger.error(f"An error occurred during the agent stream: {e}", exc_info=True)
        error_content = f"An unexpected error occurred: {e}"
        error_chunk = {
            "choices": [{"delta": {"role": "assistant", "content": error_content}, "finish_reason": "stop"}]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
    
    # Signal the end of the stream to the client
    yield "data: [DONE]\n\n"
    logger.info("Agent stream finished.")


# --- API Endpoint ---
@app.post("/v1/chat/completions")
async def chat_endpoint(request: ChatRequest):
    """
    The main API endpoint that is compatible with Open WebUI.
    """
    user_query = request.messages[-1].content if request.messages else ""
    if not user_query:
        return {"error": "No user query provided."}
    
    return StreamingResponse(stream_agent_response(user_query), media_type="text/event-stream")


# --- Main Entry Point for Running the Server ---
if __name__ == "__main__":
    logging.info("Starting CMP Copilot Agent server...")
    uvicorn.run("src.cmp_copilot.app.main:app", host="0.0.0.0", port=8000, reload=True)