USE ukaht;

ALTER TABLE ai_tags
    ADD COLUMN uncertainty_score    FLOAT        NULL,
    ADD COLUMN confidence_component FLOAT        NULL,
    ADD COLUMN quality_component    FLOAT        NULL,
    ADD COLUMN agreement_component  FLOAT        NULL,
    ADD COLUMN novelty_component    FLOAT        NULL,
    ADD COLUMN uncertainty_reason   VARCHAR(255) NULL,
    ADD COLUMN review_recommended   BOOLEAN      NOT NULL DEFAULT FALSE;

CREATE INDEX idx_ai_tags_review ON ai_tags (review_recommended, uncertainty_score);
