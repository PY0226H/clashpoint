-- virtual judge NPC action spine:
-- chat remains the room fact source; npc_service may only submit candidates.

CREATE TABLE IF NOT EXISTS debate_npc_room_configs(
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  npc_id varchar(64) NOT NULL,
  display_name varchar(64) NOT NULL DEFAULT '虚拟裁判',
  enabled boolean NOT NULL DEFAULT false,
  allow_speak boolean NOT NULL DEFAULT true,
  allow_praise boolean NOT NULL DEFAULT true,
  allow_effect boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY(session_id, npc_id)
);

CREATE INDEX IF NOT EXISTS idx_debate_npc_room_configs_enabled
  ON debate_npc_room_configs(session_id, enabled);

CREATE TABLE IF NOT EXISTS debate_npc_actions(
  id bigserial PRIMARY KEY,
  action_uid varchar(160) NOT NULL,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  npc_id varchar(64) NOT NULL,
  display_name varchar(64) NOT NULL DEFAULT '虚拟裁判',
  action_type varchar(32) NOT NULL CHECK (action_type IN ('speak', 'praise', 'effect', 'state_changed')),
  public_text text,
  target_message_id bigint REFERENCES session_messages(id) ON DELETE SET NULL,
  target_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
  target_side varchar(16) CHECK (target_side IS NULL OR target_side IN ('pro', 'con')),
  effect_kind varchar(64),
  npc_status varchar(64),
  reason_code varchar(128),
  source_event_id varchar(160),
  source_message_id bigint REFERENCES session_messages(id) ON DELETE SET NULL,
  policy_version varchar(64) NOT NULL,
  executor_kind varchar(64) NOT NULL,
  executor_version varchar(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  UNIQUE(action_uid),
  CHECK (public_text IS NULL OR char_length(public_text) <= 500)
);

CREATE INDEX IF NOT EXISTS idx_debate_npc_actions_session_created
  ON debate_npc_actions(session_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_debate_npc_actions_target_message
  ON debate_npc_actions(session_id, target_message_id, action_type)
  WHERE target_message_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_debate_npc_actions_one_praise_per_message
  ON debate_npc_actions(session_id, target_message_id, action_type)
  WHERE target_message_id IS NOT NULL AND action_type = 'praise';
