-- debate message + pin consume foundation

CREATE TABLE session_messages(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id),
  side varchar(8) NOT NULL CHECK (side IN ('pro', 'con')),
  content text NOT NULL CHECK (length(content) > 0 AND length(content) <= 1000),
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_session_messages_session_id
  ON session_messages(session_id, id DESC);
CREATE INDEX idx_session_messages_user_created
  ON session_messages(user_id, created_at DESC);

CREATE TABLE session_pinned_messages(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  message_id bigint NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id),
  ledger_id bigint NOT NULL UNIQUE REFERENCES wallet_ledger(id),
  cost_coins bigint NOT NULL CHECK (cost_coins > 0),
  pin_seconds int NOT NULL CHECK (pin_seconds >= 30 AND pin_seconds <= 600),
  pinned_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at timestamptz NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_session_pinned_messages_session_status_expires
  ON session_pinned_messages(session_id, status, expires_at DESC);
CREATE INDEX idx_session_pinned_messages_message_status
  ON session_pinned_messages(message_id, status, expires_at DESC);

-- realtime notification for debate message created
CREATE OR REPLACE FUNCTION add_to_debate_message_created()
RETURNS trigger
AS $$
DECLARE
  _user_ids bigint[];
BEGIN
  SELECT COALESCE(array_agg(user_id), '{}'::bigint[]) INTO _user_ids
  FROM session_participants
  WHERE session_id = NEW.session_id;

  PERFORM pg_notify(
    'debate_message_created',
    json_build_object(
      'message_id', NEW.id,
      'session_id', NEW.session_id,
      'user_id', NEW.user_id,
      'side', NEW.side,
      'content', NEW.content,
      'created_at', NEW.created_at,
      'user_ids', _user_ids
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_message_created_trigger ON session_messages;
CREATE TRIGGER add_to_debate_message_created_trigger
  AFTER INSERT ON session_messages
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_message_created();

-- realtime notification for debate message pinned
CREATE OR REPLACE FUNCTION add_to_debate_message_pinned()
RETURNS trigger
AS $$
DECLARE
  _user_ids bigint[];
BEGIN
  IF NEW.status <> 'active' THEN
    RETURN NEW;
  END IF;

  SELECT COALESCE(array_agg(user_id), '{}'::bigint[]) INTO _user_ids
  FROM session_participants
  WHERE session_id = NEW.session_id;

  PERFORM pg_notify(
    'debate_message_pinned',
    json_build_object(
      'pin_id', NEW.id,
      'session_id', NEW.session_id,
      'message_id', NEW.message_id,
      'user_id', NEW.user_id,
      'cost_coins', NEW.cost_coins,
      'pin_seconds', NEW.pin_seconds,
      'expires_at', NEW.expires_at,
      'user_ids', _user_ids
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_message_pinned_trigger ON session_pinned_messages;
CREATE TRIGGER add_to_debate_message_pinned_trigger
  AFTER INSERT ON session_pinned_messages
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_message_pinned();
