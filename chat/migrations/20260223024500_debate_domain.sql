-- debate domain foundation

CREATE TABLE IF NOT EXISTS debate_topics(
  id bigserial PRIMARY KEY,
  ws_id bigint NOT NULL REFERENCES workspaces(id),
  title varchar(120) NOT NULL,
  description text NOT NULL,
  category varchar(32) NOT NULL,
  stance_pro varchar(64) NOT NULL,
  stance_con varchar(64) NOT NULL,
  context_seed text,
  is_active boolean NOT NULL DEFAULT TRUE,
  created_by bigint NOT NULL REFERENCES users(id),
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_topics_ws_category_active
  ON debate_topics(ws_id, category, is_active);
CREATE INDEX IF NOT EXISTS idx_topics_ws_created_at
  ON debate_topics(ws_id, created_at DESC);

CREATE TABLE IF NOT EXISTS debate_sessions(
  id bigserial PRIMARY KEY,
  ws_id bigint NOT NULL REFERENCES workspaces(id),
  topic_id bigint NOT NULL REFERENCES debate_topics(id) ON DELETE CASCADE,
  status varchar(20) NOT NULL CHECK (status IN ('scheduled', 'open', 'running', 'judging', 'closed', 'canceled')),
  scheduled_start_at timestamptz NOT NULL,
  actual_start_at timestamptz,
  end_at timestamptz NOT NULL,
  max_participants_per_side int NOT NULL DEFAULT 500 CHECK (max_participants_per_side > 0),
  pro_count int NOT NULL DEFAULT 0 CHECK (pro_count >= 0),
  con_count int NOT NULL DEFAULT 0 CHECK (con_count >= 0),
  hot_score int NOT NULL DEFAULT 0,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  CHECK (scheduled_start_at < end_at),
  CHECK (pro_count <= max_participants_per_side),
  CHECK (con_count <= max_participants_per_side)
);

CREATE INDEX IF NOT EXISTS idx_sessions_ws_status_time
  ON debate_sessions(ws_id, status, scheduled_start_at);
CREATE INDEX IF NOT EXISTS idx_sessions_ws_topic_time
  ON debate_sessions(ws_id, topic_id, scheduled_start_at DESC);

CREATE TABLE IF NOT EXISTS session_participants(
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  side varchar(8) NOT NULL CHECK (side IN ('pro', 'con')),
  joined_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (session_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_session_side
  ON session_participants(session_id, side);
CREATE INDEX IF NOT EXISTS idx_participants_user_joined_at
  ON session_participants(user_id, joined_at DESC);

-- realtime notification for debate participant join
CREATE OR REPLACE FUNCTION add_to_debate_participant()
  RETURNS TRIGGER
  AS $$
DECLARE
  users bigint[];
  pro_cnt int;
  con_cnt int;
BEGIN
  IF TG_OP = 'INSERT' THEN
    SELECT
      ARRAY_AGG(sp.user_id),
      COUNT(*) FILTER (WHERE sp.side = 'pro')::int,
      COUNT(*) FILTER (WHERE sp.side = 'con')::int
      INTO users, pro_cnt, con_cnt
    FROM
      session_participants sp
    WHERE
      sp.session_id = NEW.session_id;

    IF users IS NULL THEN
      users := ARRAY[]::bigint[];
    END IF;

    PERFORM
      pg_notify(
        'debate_participant_joined',
        json_build_object(
          'session_id',
          NEW.session_id,
          'user_id',
          NEW.user_id,
          'side',
          NEW.side,
          'pro_count',
          pro_cnt,
          'con_count',
          con_cnt,
          'user_ids',
          users
        )::text
      );
  END IF;

  RETURN NEW;
END;
$$
LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_participant_trigger ON session_participants;
CREATE TRIGGER add_to_debate_participant_trigger
  AFTER INSERT ON session_participants
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_participant();

-- realtime notification for debate session status transition
CREATE OR REPLACE FUNCTION add_to_debate_session_status_change()
  RETURNS TRIGGER
  AS $$
DECLARE
  users bigint[];
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
    SELECT
      ARRAY_AGG(sp.user_id) INTO users
    FROM
      session_participants sp
    WHERE
      sp.session_id = NEW.id;

    IF users IS NULL THEN
      users := ARRAY[]::bigint[];
    END IF;

    PERFORM
      pg_notify(
        'debate_session_status_changed',
        json_build_object(
          'session_id',
          NEW.id,
          'from_status',
          OLD.status,
          'to_status',
          NEW.status,
          'user_ids',
          users
        )::text
      );
  END IF;

  RETURN NEW;
END;
$$
LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_session_status_change_trigger ON debate_sessions;
CREATE TRIGGER add_to_debate_session_status_change_trigger
  AFTER UPDATE ON debate_sessions
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_session_status_change();
