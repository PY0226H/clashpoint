-- ai judge domain foundation

CREATE TABLE judge_jobs(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  requested_by bigint NOT NULL REFERENCES users(id),
  status varchar(16) NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
  style_mode varchar(16) NOT NULL CHECK (style_mode IN ('rational', 'entertaining', 'mixed')),
  winner_first varchar(8) CHECK (winner_first IN ('pro', 'con', 'draw')),
  winner_second varchar(8) CHECK (winner_second IN ('pro', 'con', 'draw')),
  rejudge_triggered boolean NOT NULL DEFAULT false,
  error_message text,
  requested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_judge_jobs_session_requested
  ON judge_jobs(session_id, requested_at DESC);
CREATE INDEX idx_judge_jobs_status_requested
  ON judge_jobs(status, requested_at DESC);

CREATE TABLE judge_stage_summaries(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  job_id bigint NOT NULL REFERENCES judge_jobs(id) ON DELETE CASCADE,
  stage_no int NOT NULL CHECK (stage_no > 0),
  from_message_id bigint,
  to_message_id bigint,
  pro_score int NOT NULL CHECK (pro_score >= 0 AND pro_score <= 100),
  con_score int NOT NULL CHECK (con_score >= 0 AND con_score <= 100),
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_judge_stage_unique
  ON judge_stage_summaries(job_id, stage_no);
CREATE INDEX idx_judge_stage_session
  ON judge_stage_summaries(session_id, stage_no ASC);

CREATE TABLE judge_reports(
  id bigserial PRIMARY KEY,
  session_id bigint NOT NULL REFERENCES debate_sessions(id) ON DELETE CASCADE,
  job_id bigint NOT NULL UNIQUE REFERENCES judge_jobs(id) ON DELETE CASCADE,
  winner varchar(8) NOT NULL CHECK (winner IN ('pro', 'con', 'draw')),
  pro_score int NOT NULL CHECK (pro_score >= 0 AND pro_score <= 100),
  con_score int NOT NULL CHECK (con_score >= 0 AND con_score <= 100),
  logic_pro int NOT NULL CHECK (logic_pro >= 0 AND logic_pro <= 100),
  logic_con int NOT NULL CHECK (logic_con >= 0 AND logic_con <= 100),
  evidence_pro int NOT NULL CHECK (evidence_pro >= 0 AND evidence_pro <= 100),
  evidence_con int NOT NULL CHECK (evidence_con >= 0 AND evidence_con <= 100),
  rebuttal_pro int NOT NULL CHECK (rebuttal_pro >= 0 AND rebuttal_pro <= 100),
  rebuttal_con int NOT NULL CHECK (rebuttal_con >= 0 AND rebuttal_con <= 100),
  clarity_pro int NOT NULL CHECK (clarity_pro >= 0 AND clarity_pro <= 100),
  clarity_con int NOT NULL CHECK (clarity_con >= 0 AND clarity_con <= 100),
  pro_summary text NOT NULL,
  con_summary text NOT NULL,
  rationale text NOT NULL,
  style_mode varchar(16) NOT NULL CHECK (style_mode IN ('rational', 'entertaining', 'mixed')),
  needs_draw_vote boolean NOT NULL DEFAULT false,
  rejudge_triggered boolean NOT NULL DEFAULT false,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_judge_reports_session_created
  ON judge_reports(session_id, created_at DESC);

CREATE OR REPLACE FUNCTION add_to_debate_judge_report_ready()
RETURNS trigger
AS $$
DECLARE
  _user_ids bigint[];
BEGIN
  SELECT COALESCE(array_agg(user_id), '{}'::bigint[]) INTO _user_ids
  FROM session_participants
  WHERE session_id = NEW.session_id;

  PERFORM pg_notify(
    'debate_judge_report_ready',
    json_build_object(
      'report_id', NEW.id,
      'session_id', NEW.session_id,
      'job_id', NEW.job_id,
      'winner', NEW.winner,
      'pro_score', NEW.pro_score,
      'con_score', NEW.con_score,
      'needs_draw_vote', NEW.needs_draw_vote,
      'user_ids', _user_ids
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS add_to_debate_judge_report_ready_trigger ON judge_reports;
CREATE TRIGGER add_to_debate_judge_report_ready_trigger
  AFTER INSERT ON judge_reports
  FOR EACH ROW
  EXECUTE FUNCTION add_to_debate_judge_report_ready();
