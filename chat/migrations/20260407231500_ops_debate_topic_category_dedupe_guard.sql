CREATE INDEX IF NOT EXISTS idx_debate_topics_title_category_norm
  ON debate_topics(LOWER(BTRIM(title)), category);
