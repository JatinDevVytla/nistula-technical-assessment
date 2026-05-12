"""
Query classifier — maps a raw guest message to one of six standardised types.
Uses ordered keyword matching. Categories are checked from most specific to least specific so that edge cases like "available AND price" fall into the right bucket (pre_sales_availability takes priority here).
No ML model is used intentionally: keyword rules are transparent, fast, and easy to debug. A future version could replace this with a small Claude call for higher accuracy.
"""
import re

# Keyword maps (order matters — first match wins)
RULES = [
    (
        "complaint", [ r"\bnot working\b", r"\bbroken\b", r"\bunacceptable\b", r"\brefund\b", r"\bdisappointed\b", r"\bterrible\b",  r"\bawful\b",
           r"\bcomplain\b", r"\bno hot water\b", r"\bac not\b", r"\bpest\b", r"\bdirty\b", r"\bmosquito\b",  r"\bsmell\b", r"\bnoise\b",
        ],
    ), (
        "special_request", [ r"\bearly check.?in\b", r"\blate check.?out\b", r"\bairport transfer\b", r"\bpick.?up\b", r"\bsurprise\b",
           r"\bdecorat\b", r"\bballoon\b", r"\bcake\b", r"\bwheelchair\b", r"\baccessib\b",
        ],
    ), (
        "post_sales_checkin", [ r"\bcheck.?in time\b", r"\bcheck.?out time\b", r"\bwifi\b", r"\bwi.fi\b", r"\bpassword\b",
           r"\bdirections\b", r"\bhow to get\b", r"\bparking\b", r"\bcaretaker\b", r"\bkey\b", r"\block\b",
        ],
    ), (
        "pre_sales_availability", [ r"\bavailab\b", r"\bbook\b", r"\bdate\b", r"\bfrom .+ to\b", r"\barriv\b", r"\bstay\b", ],
    ), (
        "pre_sales_pricing", [ r"\brate\b", r"\bpric\b", r"\bcost\b", r"\bhow much\b", r"\bper night\b", r"\bcharge\b", r"\bfee\b", r"\bdiscount\b", ],
    ), (
        "general_enquiry", [],  # Default fallback — always matches if nothing else does
    ),
]

def classify_query(message: str) -> str:
    """
    Returns a query type string for a given raw message.
    Args:     message: Raw text from the guest.
    Returns:  One of the six standardised query type strings.
    """
    text = message.lower()
    for query_type, patterns in RULES:
        if not patterns:
            # This is the default fallback (general_enquiry)
            return query_type
        for pattern in patterns:
            if re.search(pattern, text): return query_type
    # Should never reach here because general_enquiry has no patterns,
    # but included as a safety net.
    return "general_enquiry"
