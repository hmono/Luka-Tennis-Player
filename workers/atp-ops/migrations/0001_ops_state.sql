-- Version 1: one primary D1 database for transactional inbox + watchdog state.
-- No replicated reads are used for admission, leases, dedup or dispatch budgets.
CREATE TABLE ops_inbox_limits (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  max_events INTEGER NOT NULL CHECK (max_events > 0),
  max_pending INTEGER NOT NULL CHECK (max_pending > 0),
  max_payload_bytes INTEGER NOT NULL CHECK (max_payload_bytes > 0)
);
INSERT INTO ops_inbox_limits VALUES (1, 10000, 1000, 8388608);

CREATE TABLE ops_inbox_totals (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  events INTEGER NOT NULL DEFAULT 0,
  pending INTEGER NOT NULL DEFAULT 0,
  payload_bytes INTEGER NOT NULL DEFAULT 0,
  quarantined INTEGER NOT NULL DEFAULT 0,
  leased INTEGER NOT NULL DEFAULT 0,
  tombstones INTEGER NOT NULL DEFAULT 0,
  audit_rows INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_successful_forward INTEGER,
  last_attempt_at INTEGER
);
INSERT INTO ops_inbox_totals (id) VALUES (1);

CREATE TABLE ops_events (
  event_id TEXT PRIMARY KEY NOT NULL,
  canonical_payload TEXT NOT NULL,
  payload_bytes INTEGER NOT NULL CHECK (payload_bytes > 0),
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','leased','forwarded','quarantined')),
  accepted_at INTEGER NOT NULL,
  due_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  lease_until INTEGER,
  last_attempt_at INTEGER,
  forwarded_at INTEGER,
  last_error TEXT,
  tombstone INTEGER NOT NULL DEFAULT 0 CHECK (tombstone IN (0,1))
);
CREATE INDEX ops_events_due ON ops_events(state, due_at, accepted_at, event_id);
CREATE INDEX ops_events_age ON ops_events(state, accepted_at);

CREATE TRIGGER ops_events_capacity BEFORE INSERT ON ops_events
WHEN NOT EXISTS (SELECT 1 FROM ops_events WHERE event_id = NEW.event_id)
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM ops_inbox_limits l JOIN ops_inbox_totals t ON t.id = l.id
    WHERE l.id = 1 AND t.events < l.max_events
      AND t.pending < l.max_pending
      AND t.payload_bytes + NEW.payload_bytes <= l.max_payload_bytes
  ) THEN RAISE(ABORT, 'inbox_capacity') END;
END;
CREATE TRIGGER ops_events_count_insert AFTER INSERT ON ops_events
BEGIN
  UPDATE ops_inbox_totals SET events = events + 1,
    pending = pending + (NEW.state != 'forwarded'),
    payload_bytes = payload_bytes + NEW.payload_bytes WHERE id = 1;
END;
CREATE TRIGGER ops_events_count_update AFTER UPDATE OF state,tombstone,last_attempt_at,forwarded_at ON ops_events
BEGIN
  UPDATE ops_inbox_totals SET pending = pending
    + (NEW.state != 'forwarded') - (OLD.state != 'forwarded'),
    quarantined = quarantined + (NEW.state = 'quarantined') - (OLD.state = 'quarantined'),
    leased = leased + (NEW.state = 'leased') - (OLD.state = 'leased'),
    tombstones = tombstones + NEW.tombstone - OLD.tombstone,
    last_successful_forward = CASE WHEN NEW.forwarded_at IS NULL THEN last_successful_forward
      ELSE max(coalesce(last_successful_forward,0),NEW.forwarded_at) END,
    last_attempt_at = CASE WHEN NEW.last_attempt_at IS NULL THEN last_attempt_at
      ELSE max(coalesce(last_attempt_at,0),NEW.last_attempt_at) END
    WHERE id = 1;
END;
-- Deletion is unsupported: preserve dedup identities until an archive protocol
-- and disaster-recovery replay horizon have been separately qualified.
CREATE TRIGGER ops_events_no_delete BEFORE DELETE ON ops_events
BEGIN SELECT RAISE(ABORT, 'dedup_retention_required'); END;

CREATE TABLE ops_forward_slots (
  slot INTEGER PRIMARY KEY,
  lease_token TEXT,
  lease_until INTEGER NOT NULL DEFAULT 0
);
INSERT INTO ops_forward_slots(slot) VALUES (0),(1),(2),(3);
CREATE TABLE ops_inbox_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL,
  at INTEGER NOT NULL,
  action TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  error_code TEXT
);
CREATE INDEX ops_inbox_audit_event ON ops_inbox_audit(event_id, at);
CREATE TRIGGER ops_audit_count_insert AFTER INSERT ON ops_inbox_audit
BEGIN
  UPDATE ops_inbox_totals SET audit_rows = audit_rows + 1,
    failures = failures + (NEW.error_code IS NOT NULL),
    attempts = attempts + (NEW.action = 'attempt') WHERE id = 1;
END;
CREATE TRIGGER ops_events_acceptance_audit AFTER INSERT ON ops_events
BEGIN
  INSERT INTO ops_inbox_audit(event_id,at,action) VALUES (NEW.event_id,NEW.accepted_at,'accepted');
END;

CREATE TABLE watchdog_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE watchdog_episodes (
  scope TEXT PRIMARY KEY,
  code TEXT NOT NULL,
  generation INTEGER NOT NULL,
  event_id TEXT NOT NULL,
  active INTEGER NOT NULL,
  opened_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  closed_at INTEGER
);
CREATE TABLE watchdog_dispatches (
  slot TEXT NOT NULL,
  attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 2),
  reserved_at INTEGER NOT NULL,
  result TEXT NOT NULL,
  PRIMARY KEY (slot, attempt)
);
