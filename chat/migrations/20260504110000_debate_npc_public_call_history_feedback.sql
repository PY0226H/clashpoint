-- virtual judge NPC public interaction loop:
-- users may call the room-visible NPC publicly; feedback remains private to product telemetry.

CREATE TABLE IF NOT EXISTS debate_npc_public_calls(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  npc_id varchar(64) NOT NULL DEFAULT 'virtual_judge_default',
  call_type varchar(32) NOT NULL CHECK (
    call_type IN (
      'rules_help',
      'issue_summary',
      'pause_review',
      'report_issue',
      'atmosphere_effect'
    )
  ),
  content text NOT NULL CHECK (char_length(BTRIM(content)) BETWEEN 1 AND 500),
  status varchar(32) NOT NULL DEFAULT 'queued' CHECK (
    status IN ('queued', 'processed', 'rejected')
  ),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debate_npc_public_calls_session_created
  ON debate_npc_public_calls(session_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_debate_npc_public_calls_user_created
  ON debate_npc_public_calls(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS debate_npc_action_feedback(
  id bigserial PRIMARY KEY,
  action_id bigint NOT NULL REFERENCES debate_npc_actions(id) ON DELETE CASCADE,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  feedback_type varchar(32) NOT NULL CHECK (
    feedback_type IN (
      'helpful',
      'too_disruptive',
      'not_neutral',
      'confusing',
      'other'
    )
  ),
  comment text CHECK (comment IS NULL OR char_length(comment) <= 300),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(action_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_debate_npc_action_feedback_session_created
  ON debate_npc_action_feedback(session_id, created_at DESC, id DESC);
