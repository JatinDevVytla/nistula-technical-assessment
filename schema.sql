-- Nistula Unified Messaging Platform
-- PostgreSQL schema
--
-- Covers:
--   - One guest profile per person, regardless of which channel they use
--   - All messages (every channel, inbound + outbound) in a single table
--   - Conversations that tie messages to guests and bookings
--   - Tracking whether a reply was AI-drafted, edited by an agent, or auto-sent
--   - Confidence score + query type stored on every inbound message

-- ENUMS

-- Channels we receive messages from
CREATE TYPE message_source AS ENUM (
    'whatsapp',
    'booking_com',
    'airbnb',
    'instagram',
    'direct'
);

-- Query categories (mirrors the classifier in src/classifier.py)
CREATE TYPE query_type AS ENUM (
    'pre_sales_availability',
    'pre_sales_pricing',
    'post_sales_checkin',
    'special_request',
    'complaint',
    'general_enquiry'
);

-- Where a message is in its lifecycle
CREATE TYPE message_status AS ENUM (
    'pending',        -- just arrived, not processed yet
    'ai_drafted',     -- Claude produced a reply, waiting for review
    'agent_edited',   -- a human changed the draft before sending
    'auto_sent',      -- sent automatically (confidence >= 0.85)
    'agent_sent',     -- sent manually by a team member
    'escalated'       -- flagged for urgent attention
);

-- What the confidence scorer recommends
CREATE TYPE recommended_action AS ENUM ( 'auto_send', 'agent_review', 'escalate' );


-- PROPERTIES

-- Simple lookup table for villas.
-- Messages and reservations both reference this.
CREATE TABLE properties (
    id              VARCHAR(50)   PRIMARY KEY,       -- e.g. "villa-b1"
    name            VARCHAR(255)  NOT NULL,
    location        VARCHAR(255),
    bedrooms        INTEGER,
    max_guests      INTEGER,
    base_rate_inr   NUMERIC(10, 2),
    extra_guest_fee NUMERIC(10, 2),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- GUESTS

-- One row per real person, not one row per channel.
-- A guest who books on Airbnb and then messages on WhatsApp
-- should still be one record — so we store all their identifiers here.
--
-- The trade-off: matching an inbound message to an existing guest
-- means checking across several columns. That logic lives in the
-- application layer as an upsert on first contact.
CREATE TABLE guests (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           VARCHAR(255)  NOT NULL,
    email               VARCHAR(255)  UNIQUE,
    phone               VARCHAR(50)   UNIQUE,
    whatsapp_id         VARCHAR(100)  UNIQUE,
    airbnb_user_id      VARCHAR(100)  UNIQUE,
    booking_com_user_id VARCHAR(100)  UNIQUE,
    instagram_handle    VARCHAR(100)  UNIQUE,
    notes               TEXT,                        -- internal team notes
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_guests_full_name ON guests (full_name);

-- RESERVATIONS

-- One row per booking. Ties a guest to a property + date range.
CREATE TABLE reservations (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     VARCHAR(50)   UNIQUE NOT NULL,   -- e.g. "NIS-2024-0891"
    guest_id        UUID          NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
    property_id     VARCHAR(50)   NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
    check_in        DATE          NOT NULL,
    check_out       DATE          NOT NULL,
    guest_count     INTEGER       NOT NULL DEFAULT 1,
    total_amount    NUMERIC(12, 2),
    status          VARCHAR(50)   NOT NULL DEFAULT 'confirmed',  -- confirmed / cancelled / completed
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_dates       CHECK (check_out > check_in),
    CONSTRAINT valid_guest_count CHECK (guest_count >= 1)
);

CREATE INDEX idx_reservations_booking_ref ON reservations (booking_ref);
CREATE INDEX idx_reservations_guest_id    ON reservations (guest_id);
CREATE INDEX idx_reservations_property_id ON reservations (property_id);

-- CONVERSATIONS

-- Groups related messages into a thread.
-- Exists separately from messages so the team can read a full
-- exchange in one place rather than hunting through individual rows.

-- reservation_id is nullable on purpose — guests often enquire
-- before they have a booking, so we can't always link to one.
CREATE TABLE conversations (
    id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID          NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
    reservation_id  UUID          REFERENCES reservations(id) ON DELETE SET NULL,
    property_id     VARCHAR(50)   REFERENCES properties(id) ON DELETE SET NULL,
    subject         VARCHAR(255),
    is_resolved     BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_guest_id       ON conversations (guest_id);
CREATE INDEX idx_conversations_reservation_id ON conversations (reservation_id);


-- MESSAGES

-- Every message sent or received, across every channel, in one table.

-- A few deliberate choices worth noting:

-- raw_message is always preserved exactly as received.
-- normalised_message is the cleaned version we pass to Claude.
-- Both are stored so we can debug cases where the AI reply seems off —
-- you need to see exactly what Claude was given.

-- ai_drafted_reply and final_reply are stored separately.
-- If an agent edits the draft, we keep both so we can track
-- how often and how much humans are changing AI output.
-- That's a useful quality signal over time.

-- query_type and ai_confidence_score are NULL on outbound messages —
-- those fields only apply to things guests sent us.

CREATE TABLE messages (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID                NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    guest_id            UUID                NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
    source              message_source      NOT NULL,
    direction           VARCHAR(10)         NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    raw_message         TEXT                NOT NULL,
    normalised_message  TEXT,
    query_type          query_type,
    ai_confidence_score NUMERIC(4, 3),               -- 0.000 to 1.000
    ai_drafted_reply    TEXT,
    final_reply         TEXT,
    status              message_status      NOT NULL DEFAULT 'pending',
    recommended_action  recommended_action,
    guest_sent_at       TIMESTAMPTZ,
    processed_at        TIMESTAMPTZ,
    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    CONSTRAINT confidence_range CHECK ( ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 1) )
);

CREATE INDEX idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX idx_messages_guest_id        ON messages (guest_id);
CREATE INDEX idx_messages_status          ON messages (status);
CREATE INDEX idx_messages_query_type      ON messages (query_type);
CREATE INDEX idx_messages_source          ON messages (source);
CREATE INDEX idx_messages_guest_sent_at   ON messages (guest_sent_at DESC);


-- AGENT ACTIONS

-- Audit log for anything a team member does to a message.
-- Useful for performance reviews and spotting patterns
-- (e.g. one agent is editing every AI reply — why?).
CREATE TABLE agent_actions (
    id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id  UUID          NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    agent_email VARCHAR(255)  NOT NULL,
    action      VARCHAR(50)   NOT NULL,   -- "edited", "approved", "escalated", "sent"
    notes       TEXT,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_actions_message_id ON agent_actions (message_id);
