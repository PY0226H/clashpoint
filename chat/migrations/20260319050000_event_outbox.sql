-- event outbox for reliable kafka producer delivery (at-least-once)

CREATE TABLE event_outbox(
  id bigserial PRIMARY KEY,
  event_id varchar(64) NOT NULL UNIQUE,
  event_type varchar(128) NOT NULL,
  source varchar(64) NOT NULL,
  aggregate_id varchar(128) NOT NULL,
  topic varchar(128) NOT NULL,
  partition_key varchar(256) NOT NULL,
  payload jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  status varchar(16) NOT NULL CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
  attempts int NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  available_at timestamptz NOT NULL DEFAULT NOW(),
  locked_until timestamptz,
  last_error text,
  sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_event_outbox_due
  ON event_outbox(status, available_at, locked_until, id);

CREATE INDEX idx_event_outbox_unsent
  ON event_outbox(status, updated_at DESC);
