-- durable websocket replay stream for debate room events

CREATE TABLE debate_room_events(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  event_seq bigint NOT NULL CHECK (event_seq > 0),
  event_name text NOT NULL,
  dedupe_key text NOT NULL,
  payload jsonb NOT NULL,
  event_at timestamptz NOT NULL DEFAULT NOW(),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(session_id, event_seq),
  UNIQUE(session_id, event_name, dedupe_key)
);

CREATE INDEX idx_debate_room_events_session_seq
  ON debate_room_events(session_id, event_seq DESC);

CREATE INDEX idx_debate_room_events_session_event_at
  ON debate_room_events(session_id, event_at DESC);
