-- notify participants when draw-vote reaches a terminal decision

CREATE OR REPLACE FUNCTION add_to_debate_draw_vote_resolved()
RETURNS trigger
AS $$
DECLARE
  _user_ids bigint[];
  _participated_voters int;
  _agree_votes int;
  _disagree_votes int;
BEGIN
  IF OLD.status = 'open' AND NEW.status <> 'open' THEN
    SELECT COALESCE(array_agg(user_id), '{}'::bigint[]) INTO _user_ids
    FROM session_participants
    WHERE session_id = NEW.session_id;

    SELECT
      COUNT(*)::int,
      COUNT(*) FILTER (WHERE agree_draw)::int,
      COUNT(*) FILTER (WHERE NOT agree_draw)::int
    INTO _participated_voters, _agree_votes, _disagree_votes
    FROM judge_draw_vote_ballots
    WHERE vote_id = NEW.id;

    PERFORM pg_notify(
      'debate_draw_vote_resolved',
      json_build_object(
        'vote_id', NEW.id,
        'session_id', NEW.session_id,
        'report_id', NEW.report_id,
        'status', NEW.status,
        'resolution', NEW.resolution,
        'participated_voters', COALESCE(_participated_voters, 0),
        'agree_votes', COALESCE(_agree_votes, 0),
        'disagree_votes', COALESCE(_disagree_votes, 0),
        'required_voters', NEW.required_voters,
        'decided_at', NEW.decided_at,
        'rematch_session_id', NEW.rematch_session_id,
        'user_ids', _user_ids
      )::text
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_draw_vote_resolved_trigger ON judge_draw_votes;
CREATE TRIGGER add_to_debate_draw_vote_resolved_trigger
  AFTER UPDATE ON judge_draw_votes
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_draw_vote_resolved();
