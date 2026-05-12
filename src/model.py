"""  Pydantic models for request validation and response serialisation. """

from pydantic import BaseModel, Field
from typing import Literal, Optional

# Valid channels the system can receive messages from
SOURCE_CHANNELS = Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"]

# All recognised query categories
QUERY_TYPES = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
]

# Actions that can be taken on a drafted reply
ACTIONS = Literal["auto_send", "agent_review", "escalate"]

class InboundMessage(BaseModel):
    """Raw message payload arriving from any channel."""
    source:       SOURCE_CHANNELS = Field(..., description="Channel the message arrived from")
    guest_name:   str             = Field(..., min_length=1, description="Full name of the guest")
    message:      str             = Field(..., min_length=1, description="Raw message text from the guest")
    timestamp:    str             = Field(..., description="ISO 8601 timestamp of when the message was sent")
    booking_ref:  Optional[str]   = Field(None, description="Reservation reference, if known")
    property_id:  Optional[str]   = Field(None, description="Property identifier, if known")
    model_config = {
        "json_schema_extra": {
            "example": {
                "source"     : "whatsapp",
                "guest_name" : "Rahul Sharma",
                "message"    : "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
                "timestamp"  : "2026-05-05T10:30:00Z",
                "booking_ref": "NIS-2024-0891",
                "property_id": "villa-b1",
            }
        }
    }

class WebhookResponse(BaseModel):
    """Structured response returned after processing a guest message."""
    message_id:       str         = Field(..., description="UUID generated for this message")
    query_type:       QUERY_TYPES = Field(..., description="Classified type of the guest's query")
    drafted_reply:    str         = Field(..., description="AI-drafted reply ready for review or sending")
    confidence_score: float       = Field(..., ge=0.0, le=1.0, description="Score between 0 and 1")
    action:           ACTIONS     = Field(..., description="Recommended action based on confidence score")
