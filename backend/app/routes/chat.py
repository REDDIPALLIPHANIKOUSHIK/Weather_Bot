import logging
from fastapi import APIRouter
from ..models import ChatRequest, ChatResponse
from ..services.advisory import AdvisoryCoordinator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])
coordinator = AdvisoryCoordinator()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.info("Received chat query for session '%s': %s", request.session_id, request.message[:60])
    response = await coordinator.run(
        session_id=request.session_id,
        message=request.message,
        current_location=request.current_location,
        language=request.language,
    )
    return response
