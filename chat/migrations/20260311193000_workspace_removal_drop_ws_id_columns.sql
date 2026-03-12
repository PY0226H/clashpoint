-- Workspace removal W4:
-- Drop legacy tenant key columns reintroduced by single-tenant compat shim.

ALTER TABLE users
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE chats
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE debate_topics
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE debate_sessions
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE session_messages
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE session_pinned_messages
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE judge_jobs
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE judge_stage_summaries
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE judge_reports
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE judge_draw_votes
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE judge_draw_vote_ballots
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE iap_orders
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE user_wallets
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE wallet_ledger
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE kafka_dlq_events
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE auth_refresh_sessions
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE ops_alert_notifications
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE ops_alert_states
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE ops_observability_configs
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE ops_service_split_reviews
  DROP COLUMN IF EXISTS ws_id;

ALTER TABLE ops_service_split_review_audits
  DROP COLUMN IF EXISTS ws_id;
