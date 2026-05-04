-- virtual judge NPC ops control plane:
-- chat owns room-level enablement, status, and capability gates.

ALTER TABLE debate_npc_room_configs
  ADD COLUMN IF NOT EXISTS persona_style varchar(64) NOT NULL DEFAULT 'balanced_host',
  ADD COLUMN IF NOT EXISTS status varchar(32) NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS allow_state_change boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS allow_warning boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS allow_public_call boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS allow_pause boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS manual_takeover_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS status_reason varchar(128),
  ADD COLUMN IF NOT EXISTS updated_by_user_id bigint REFERENCES users(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_debate_npc_room_configs_status'
  ) THEN
    ALTER TABLE debate_npc_room_configs
      ADD CONSTRAINT ck_debate_npc_room_configs_status
      CHECK (status IN ('active', 'silent', 'manual_takeover', 'unavailable'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_debate_npc_room_configs_persona_style'
  ) THEN
    ALTER TABLE debate_npc_room_configs
      ADD CONSTRAINT ck_debate_npc_room_configs_persona_style
      CHECK (char_length(BTRIM(persona_style)) BETWEEN 1 AND 64);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'ck_debate_npc_room_configs_status_reason'
  ) THEN
    ALTER TABLE debate_npc_room_configs
      ADD CONSTRAINT ck_debate_npc_room_configs_status_reason
      CHECK (status_reason IS NULL OR char_length(status_reason) <= 128);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_debate_npc_room_configs_status
  ON debate_npc_room_configs(session_id, status);
