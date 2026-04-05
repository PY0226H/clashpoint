-- govern debate_message_pinned trigger under kafka-only notify ingress
-- when notify service is in kafka-only mode, outbox/kafka becomes the
-- single primary event source and pg_notify for pinned events is suppressed.

CREATE OR REPLACE FUNCTION add_to_debate_message_pinned()
RETURNS trigger
AS $$
DECLARE
  _user_ids bigint[];
  _kafka_only_ingress boolean;
BEGIN
  IF NEW.status <> 'active' THEN
    RETURN NEW;
  END IF;

  SELECT EXISTS(
    SELECT 1
    FROM notify_runtime_signals
    WHERE kafka_enabled = true
      AND disable_pg_listener = true
      AND updated_at >= NOW() - INTERVAL '120 seconds'
  ) INTO _kafka_only_ingress;

  IF _kafka_only_ingress THEN
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
