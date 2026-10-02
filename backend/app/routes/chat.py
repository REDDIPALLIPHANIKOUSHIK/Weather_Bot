import logging
from fastapi import APIRouter
from ..models import ChatRequest, ChatResponse
from ..graph import run_advisory_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.info("LangGraph chat query for session '%s': %s (lang: %s)", request.session_id, request.message[:60], request.language)
    response = await run_advisory_graph(
        session_id=request.session_id,
        message=request.message,
        current_location=request.current_location,
        language=request.language,
    )
    return response
