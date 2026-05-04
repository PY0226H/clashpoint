ALTER TABLE debate_npc_actions
  DROP CONSTRAINT IF EXISTS debate_npc_actions_action_type_check;

ALTER TABLE debate_npc_actions
  ADD CONSTRAINT debate_npc_actions_action_type_check
  CHECK (action_type IN ('speak', 'praise', 'effect', 'state_changed', 'pause_suggestion'));
