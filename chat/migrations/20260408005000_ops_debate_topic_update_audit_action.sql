ALTER TABLE ops_debate_topic_audits
DROP CONSTRAINT IF EXISTS ops_debate_topic_audits_action_check;

ALTER TABLE ops_debate_topic_audits
ADD CONSTRAINT ops_debate_topic_audits_action_check
CHECK (action IN ('create', 'create_replay', 'update'));
