"""
AI handler — builds a structured prompt and calls the Claude API to draft a guest reply. Returns the reply text plus raw factors used for confidence scoring.
"""
import os
import httpx
import logging
from typing import Tuple
logger = logging.getLogger(__name__)

# Property context (hardcoded per brief — in production this would come from DB) ──
PROPERTY_CONTEXT = """
Property: Villa B1, Assagao, North Goa
Bedrooms: 3 | Max guests: 6 | Private pool: Yes
Check-in: 2pm | Check-out: 11am
Base rate: INR 18,000 per night (up to 4 guests)
Extra guest charge: INR 2,000 per night per person
WiFi password: Nistula@2024
Caretaker: Available 8am to 10pm
Chef on call: Yes, pre-booking required
Availability April 20–24: Available
Cancellation policy: Free cancellation up to 7 days before check-in
""".strip()

SYSTEM_PROMPT = """
You are a professional, warm, and concise guest relations assistant for Nistula, a luxury villa rental company in Goa, India.
Your job is to draft a reply to a guest message on behalf of the Nistula team.
Rules: - Be warm and personal — always use the guest's first name.
       - Be accurate — only use information from the property context provided.
       - Be concise — no unnecessary filler. Guests value clarity.
       - Never invent prices, availability, or policies.
       - If you cannot answer something fully from the context, say you will confirm shortly rather than guessing.
       - End with a friendly closing line that invites a follow-up if needed.
"""


def _build_user_prompt(normalised: dict) -> Tuple[str, dict]:
    """
    Constructs the user-facing prompt sent to Claude.
    Also returns metadata used later for confidence scoring.
    """
    guest_name  = normalised["guest_name"].split()[0]  # First name only
    query_type  = normalised["query_type"]
    source      = normalised["source"]
    booking_ref = normalised.get("booking_ref") or "Not provided"
    prompt = f""" Property context: {PROPERTY_CONTEXT}

Guest name:        {normalised['guest_name']}
Channel:           {source}
Query type:        {query_type}
Booking reference: {booking_ref}
Timestamp:         {normalised['timestamp']}

Guest message: \"\"\"{normalised['message_text']}\"\"\"

Draft a reply addressing the guest's message. Address the guest by first name ({guest_name}).""".strip()
    metadata = {
        "query_type": query_type,
        "has_booking_ref": booking_ref != "Not provided",
        "source": source,
    }

    return prompt, metadata

async def get_ai_reply(normalised: dict) -> Tuple[str, dict]:
    """
    Sends the normalised message to Claude and returns:
    - drafted_reply       (str): the AI-drafted reply text
    - confidence_factors (dict): raw metadata passed to the confidence scorer
    Raises: HTTPException-compatible exception on API failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key: raise EnvironmentError("ANTHROPIC_API_KEY is not set in environment variables.")
    user_prompt, metadata = _build_user_prompt(normalised)
    payload = {
        "model"      : "claude-sonnet-4-20250514",
        "max_tokens" : 1000,
        "system"     : SYSTEM_PROMPT,
        "messages"   : [ {"role": "user", "content": user_prompt} ],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("Claude API request timed out.")
            raise RuntimeError("AI service timed out. Please try again.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API error: {e.response.status_code} — {e.response.text}")
            raise RuntimeError(f"AI service returned an error: {e.response.status_code}")

    data = response.json()

    # Extract the text content from the Claude response
    reply_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text": reply_text += block["text"]

    if not reply_text: raise RuntimeError("Claude returned an empty response.")

    # Add token usage to metadata for confidence scoring
    usage = data.get("usage", {})
    metadata["output_tokens"] = usage.get("output_tokens", 0)
    metadata["stop_reason"] = data.get("stop_reason", "")

    return reply_text.strip(), metadata
