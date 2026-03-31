-- add syncRequired reason counters for notify replay recovery observability

ALTER TABLE notify_runtime_signals
  ADD COLUMN sync_required_persist_failed_total bigint NOT NULL DEFAULT 0;

ALTER TABLE notify_runtime_signals
  ADD COLUMN sync_required_replay_storage_unavailable_total bigint NOT NULL DEFAULT 0;

ALTER TABLE notify_runtime_signals
  ADD CONSTRAINT chk_notify_runtime_sync_required_persist_failed_non_negative
  CHECK (sync_required_persist_failed_total >= 0);

ALTER TABLE notify_runtime_signals
  ADD CONSTRAINT chk_notify_runtime_sync_required_replay_storage_unavailable_non_negative
  CHECK (sync_required_replay_storage_unavailable_total >= 0);
