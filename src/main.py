"""
=Guest Message Handler
FastAPI backend that receives guest messages, normalises them, drafts AI replies via Claude, and returns a confidence score.
"""

import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import InboundMessage, WebhookResponse
from classifier import classify_query
from ai_handler import get_ai_reply
from confidence import calculate_confidence

# Logging Set-Up
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
) 

logger = logging.getLogger(__name__)

# App setup
app = FastAPI(
    title="Nistula Guest Message Handler",
    description="Receives, normalises, and drafts replies to guest messages.",
    version="1.0.0"
) 
app.add_middleware (
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Health check
@app.get("/")
async def root(): return {"status": "ok", "service": "Nistula Guest Message Handler"}

# Main webhook endpoint
@app.post("/webhook/message", response_model=WebhookResponse)
async def handle_message(payload: InboundMessage):
    """
    Receives a raw guest message, normalises it, classifies the query type, gets a drafted reply from Claude, and returns a structured response.
    """
    logger.info(f"Incoming message from {payload.source} | guest: {payload.guest_name}")

    # Step 1 — Generate a unique message ID
    message_id = str(uuid.uuid4())
    # Step 2 — Classify the query type from the message text
    query_type = classify_query(payload.message)
    logger.info(f"Classified as: {query_type}")
    # Step 3 — Build the unified normalised schema
    normalised = {
        "message_id": message_id,
        "source": payload.source,
        "guest_name": payload.guest_name,
        "message_text": payload.message,
        "timestamp": payload.timestamp,
        "booking_ref": payload.booking_ref,
        "property_id": payload.property_id,
        "query_type": query_type,
    }
    # Step 4 — Get drafted reply from Claude
    drafted_reply, raw_confidence_factors = await get_ai_reply(normalised)
    # Step 5 — Calculate confidence score
    confidence_score = calculate_confidence(query_type, raw_confidence_factors)
    # Step 6 — Determine action based on score and query type
    if query_type == "complaint" or confidence_score < 0.60: action = "escalate"
    elif confidence_score >= 0.85: action = "auto_send"
    else: action = "agent_review"
    logger.info(f"Reply drafted | confidence: {confidence_score} | action: {action}")
    return WebhookResponse(
        message_id=message_id,
        query_type=query_type,
        drafted_reply=drafted_reply,
        confidence_score=round(confidence_score, 2),
        action=action,
    )

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse( status_code=500, content={"error": "Internal server error. Please try again later."} )
