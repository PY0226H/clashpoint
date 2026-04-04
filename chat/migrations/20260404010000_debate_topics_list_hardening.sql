-- normalize debate topic category and add list hot-path indexes

UPDATE debate_topics
SET category = LOWER(BTRIM(category))
WHERE category <> LOWER(BTRIM(category));

CREATE INDEX IF NOT EXISTS idx_topics_active_created_at_id_desc
  ON debate_topics(is_active, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_topics_category_active_created_at_id_desc
  ON debate_topics(category, is_active, created_at DESC, id DESC);
