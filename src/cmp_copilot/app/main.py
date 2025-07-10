
import logging
import json
import uvicorn
import os
import uuid
import asyncio
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from ..core.agent import create_agent_graph

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the agent's lifecycle. It's called once when the server starts.
    """
    logger.info("Server starting up...")
    db_conn_str = (
        f"postgresql://postgres:{os.getenv('DB_PASSWORD', 'agent')}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
        f"/{os.getenv('DB_NAME', 'agent_db')}"
    )
    checkpointer_manager = AsyncPostgresSaver.from_conn_string(db_conn_str)
    checkpointer = await checkpointer_manager.__aenter__()
    app.state.checkpointer_manager = checkpointer_manager
    app.state.checkpointer = checkpointer
    uncompiled_graph = create_agent_graph()
    app.state.agent_graph = uncompiled_graph.compile(checkpointer=checkpointer)
    logger.info("Agent graph compiled with PostgreSQL checkpointer.")
    yield
    logger.info("Server shutting down...")
    if hasattr(app.state, "checkpointer_manager"):
        await app.state.checkpointer_manager.__aexit__(None, None, None)

app = FastAPI(
    title="CMP Copilot Agent",
    description="An agentic AI for cloud management and security scanning.",
    version="2.5.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str

async def stream_agent_response(user_query: Any, thread_id: str):
    """
    This async generator calls the agent for a specific thread and yields
    formatted chunks for the UI.
    """
    logger.info(f"Starting agent stream for query: '{user_query}' in thread: {thread_id}")
    inputs = {"user_query": user_query}
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        async for event in app.state.agent_graph.astream(inputs, config):
            for node_name, node_output in event.items():
                if "messages" in node_output:
                    for role, content in node_output["messages"]:
                        content_str = str(content) if content is not None else ""
                        chunk = {"choices": [{"delta": {"role": "assistant", "content": content_str}}]}
                        yield f"data: {json.dumps(chunk)}\n\n"
        
    except Exception as e:
        logger.error(f"An error occurred during the agent stream: {e}", exc_info=True)
        error_content = f"An unexpected error occurred: {e}"
        error_chunk = {"choices": [{"delta": {"role": "assistant", "content": error_content}, "finish_reason": "stop"}]}
        yield f"data: {json.dumps(error_chunk)}\n\n"
    
    yield "data: [DONE]\n\n"
    logger.info(f"Agent stream finished for thread: {thread_id}")

@app.post("/v1/chat/completions")
async def chat_endpoint(request: ChatRequest):
    """
    The main endpoint for user queries. It now uses a consistent thread_id
    to maintain conversational state.
    """
    user_query = request.messages[-1].content if request.messages else ""
    if not user_query:
        return {"error": "No user query provided."}
    
    thread_id = "main_persistent_chat_session"
    
    return StreamingResponse(stream_agent_response(user_query, thread_id), media_type="text/event-stream")

@app.get("/v1/acknowledge/{report_id}", response_class=HTMLResponse)
async def acknowledge_endpoint(report_id: str):
    """
    This webhook is triggered by the link in the notification email.
    """
    logger.info(f"Acknowledgment received for report_id: {report_id}")
    config = {"configurable": {"thread_id": report_id}}
    inputs = {"user_query": {"action": "initiate_cloning", "report_id": report_id}}
    asyncio.create_task(app.state.agent_graph.ainvoke(inputs, config))
    return """
    <html><head><title>Acknowledgment Received</title></head>
    <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h1>Thank You!</h1>
        <p>Your acknowledgment for report <strong>{report_id}</strong> has been received.</p>
        <p>The forensic cloning process has been initiated and will run in the background.</p>
    </body></html>
    """.format(report_id=report_id)

if __name__ == "__main__":
    logging.info("Starting CMP Copilot Agent server...")
    uvicorn.run("src.cmp_copilot.app.main:app", host="0.0.0.0", port=8000, reload=True)
