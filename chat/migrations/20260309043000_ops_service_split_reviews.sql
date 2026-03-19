CREATE TABLE ops_service_split_reviews(
  singleton_id smallint PRIMARY KEY DEFAULT 1 CHECK (singleton_id = 1),
  payment_compliance_required boolean,
  review_note text NOT NULL DEFAULT '',
  updated_by bigint NOT NULL REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ops_service_split_reviews_updated_at
  ON ops_service_split_reviews(updated_at DESC);
