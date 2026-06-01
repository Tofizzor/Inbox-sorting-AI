-- SQLite schema for AI Inbox triage (Phase 1)

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sender TEXT,
    received_at TEXT,
    source TEXT NOT NULL DEFAULT 'api',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    reason TEXT NOT NULL,
    destination TEXT NOT NULL,
    extracted_fields TEXT NOT NULL,
    model_name TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analyses_message_id ON analyses(message_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(message_id, created_at DESC);

CREATE TABLE IF NOT EXISTS analysis_attempts (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id),
    attempt_number INTEGER NOT NULL,
    raw_llm_response TEXT,
    error_type TEXT NOT NULL,
    error_detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analysis_attempts_message_id ON analysis_attempts(message_id);

CREATE TABLE IF NOT EXISTS guide_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    config TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    payload TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);

-- Phase 2: AI-drafted replies with a human approval gate.
-- Lifecycle: draft -> edited -> approved -> sent. Regenerating creates a new row.
-- Nothing is ever sent unless status = 'approved' (enforced in services + a 409 guard).
CREATE TABLE IF NOT EXISTS draft_replies (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id),
    analysis_id TEXT REFERENCES analyses(id),
    generated_text TEXT NOT NULL,
    edited_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    tone TEXT NOT NULL DEFAULT 'professional',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    approved_by TEXT,
    sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_draft_replies_message_id ON draft_replies(message_id);
CREATE INDEX IF NOT EXISTS idx_draft_replies_status ON draft_replies(status);

-- Failed reply-generation attempts (mirrors analysis_attempts): garbage AI output is
-- logged here for audit instead of being persisted as a usable draft.
CREATE TABLE IF NOT EXISTS reply_attempts (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id),
    attempt_number INTEGER NOT NULL,
    raw_llm_response TEXT,
    error_type TEXT NOT NULL,
    error_detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reply_attempts_message_id ON reply_attempts(message_id);
