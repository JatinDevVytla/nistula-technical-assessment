# Nistula Technical Assessment
Guest message handler for Nistula's unified messaging platform.
Built with **Python + FastAPI**. Receives raw guest messages, normalises them into a unified schema, classifies the query type, drafts a reply using the Claude API, and returns a confidence score with a recommended action.

---
## What's in this repository
```
nistula-technical-assessment/
├── src/
│   ├── main.py          ← FastAPI app and /webhook/message endpoint
│   ├── models.py        ← Pydantic request/response models
│   ├── classifier.py    ← Keyword-based query type classifier
│   ├── ai_handler.py    ← Claude API integration and prompt builder
│   └── confidence.py    ← Confidence scoring logic
├── schema.sql           ← Part 2: PostgreSQL schema with comments
├── thinking.md          ← Part 3: Thinking question answers
├── requirements.txt
├── .env.example
└── README.md
```
---

## Setup

**Requirements:** Python 3.11+

### 1. Clone the repository
```bash
git clone https://github.com/your-username/nistula-technical-assessment.git
cd nistula-technical-assessment
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate      # Mac / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```
Open `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your_key_here
```

### 5. Run the server
```bash
cd src
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`.

---

## Using the endpoint
### POST /webhook/message
Send a guest message and receive a drafted reply.
```bash
curl -X POST http://localhost:8000/webhook/message \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1"
  }'
```

**Response:**
```json
{
  "message_id": "a3f1c2d4-...",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news — Villa B1 is available from April 20 to 24...",
  "confidence_score": 0.95,
  "action": "auto_send"
}
```
---

## Test inputs
Three sample payloads covering different query types and channels:

**1. Availability + pricing enquiry (WhatsApp)**
```json
{
  "source": "whatsapp",
  "guest_name": "Rahul Sharma",
  "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
  "timestamp": "2026-05-05T10:30:00Z",
  "booking_ref": "NIS-2024-0891",
  "property_id": "villa-b1"
}
```
**2. Post-booking check-in query (Airbnb)**
```json
{
  "source": "airbnb",
  "guest_name": "Priya Menon",
  "message": "Hi, what time can we check in? Also, what is the WiFi password?",
  "timestamp": "2026-05-10T08:15:00Z",
  "booking_ref": "NIS-2024-1102",
  "property_id": "villa-b1"
}
```
**3. Complaint (Direct)**
```json
{
  "source": "direct",
  "guest_name": "James Carter",
  "message": "The AC is not working and the pool is dirty. This is completely unacceptable.",
  "timestamp": "2026-05-11T03:22:00Z",
  "booking_ref": "NIS-2024-0765",
  "property_id": "villa-b1"
}
```

---

## Confidence scoring logic

The confidence score represents how reliably the system can handle a message without human review. It is not a measure of how good Claude's reply is — it is a measure of how safe it is to send that reply automatically.

### How it is calculated

**Step 1 — Base score by query type**:

Each query type starts with a base score reflecting how answerable it typically is from structured property data:

| Query type               | Base score | Reasoning |
|--------------------------|------------|-----------|
| pre_sales_availability   | 0.90       | Factual — checked against property data |
| pre_sales_pricing        | 0.88       | Factual — rates are fixed and documented |
| post_sales_checkin       | 0.85       | Mostly factual like WiFi, check-in times) |
| general_enquiry          | 0.75       | Varies — may not always have a full answer |
| special_request          | 0.65       | Often needs human approval |
| complaint                | 0.40       | Always escalated — human must handle |

**Step 2 — Context completeness bonus**: If the guest included a booking reference, we have more context to work from. Score increases by +0.05.

**Step 3 — Reply quality check**:
- If Claude produced fewer than 50 output tokens, the reply may be too short or vague. Score decreases by -0.15.
- If Claude stopped for an unexpected reason (not `end_turn`), something went wrong. Score decreases by -0.10.

**Step 4 — Action decision**
| Score range       | Action        |
|-------------------|---------------|
| ≥ 0.85            | auto_send     |
| 0.60 – 0.84       | agent_review  |
| < 0.60            | escalate      |
| Any complaint     | escalate      |
Complaints always escalate regardless of score because they require human judgement on empathy, compensation, and resolution — things an AI should not decide alone.
---

## Error handling
- Missing or invalid fields return a `422 Unprocessable Entity` with details.
- Claude API errors (timeout, rate limit, bad status) are caught and return a `500` with a clean message.
- A missing `ANTHROPIC_API_KEY` raises a startup-time `EnvironmentError` with a clear description.
- All errors are logged to stdout with timestamps.

---

## Interactive docs
FastAPI's built-in docs are available at: `http://localhost:8000/docs`
These let you test the endpoint directly from your browser without needing curl.
