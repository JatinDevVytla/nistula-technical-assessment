"""
Confidence scorer — produces a float between 0 and 1.
Confidence is NOT just "how long is the reply" or a random number. It reflects how reliably the system can handle a message WITHOUT human review.
Three factors combine to produce the final score:
1. Query type base score
     Some query types are inherently more answerable from structured data (e.g. availability, pricing) than others (e.g. complaints, special requests which require human judgement).
     We assign a starting confidence per type.
2. Context completeness bonus
     If the guest provided a booking reference, we have more context to work from, which increases confidence slightly.
3. Reply quality penalty
     If Claude's output was very short (< 50 tokens), it may have been a non-answer. We penalise accordingly.
     If Claude stopped for a reason other than "end_turn", something went wrong, so we penalise.
Score interpretation
>= 0.85   → auto_send       (safe to send without human review)
0.60–0.84 → agent_review    (a human should check before sending)
< 0.60    → escalate        (requires human attention immediately)
Complaints always escalate regardless of score.
"""

# Base confidence per query type
BASE_SCORES = {
    "pre_sales_availability": 0.90,  # Highly factual:   answered from property data
    "pre_sales_pricing":      0.88,  # Factual:          rates are fixed
    "post_sales_checkin":     0.85,  # Mostly factual:   like WiFi, times, directions
    "general_enquiry":        0.75,  # Varies:           may not always have a clear answer
    "special_request":        0.65,  # Needs human approval in most cases
    "complaint":              0.40,  # Always escalated: human must handle
}

def calculate_confidence(query_type: str, factors: dict) -> float:
    """
    Calculates and returns a confidence score between 0.0 and 1.0.
    Args:
        query_type: Classified query type string.
        factors: Dict of metadata from the AI handler (tokens, stop reason, etc.)
    Returns: Float between 0.0 and 1.0.
    """
    score = BASE_SCORES.get(query_type, 0.70)

    # Bonus: guest provided a booking reference → more context available
    if factors.get("has_booking_ref"): score += 0.05
  
    # Penalty: reply was very short → may be a vague or incomplete answer
    output_tokens = factors.get("output_tokens", 100)
    if output_tokens < 50: score -= 0.15
  
    # Penalty: Claude stopped for an unexpected reason
    stop_reason = factors.get("stop_reason", "end_turn")
    if stop_reason != "end_turn": score -= 0.10
  
    # Clamp to valid range [0.0, 1.0]
    return round(max(0.0, min(1.0, score)), 2)
