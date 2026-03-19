CREATE TABLE ops_service_split_review_audits(
  id bigserial PRIMARY KEY,
  payment_compliance_required boolean,
  review_note text NOT NULL DEFAULT '',
  updated_by bigint NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_service_split_review_audits_created_at
  ON ops_service_split_review_audits(created_at DESC, id DESC);
