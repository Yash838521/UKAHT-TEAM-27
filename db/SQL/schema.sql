CREATE DATABASE IF NOT EXISTS ukaht;
USE ukaht;

CREATE TABLE images (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    filename        VARCHAR(255) NOT NULL,
    storage_url     VARCHAR(500) NOT NULL,
    uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed       BOOLEAN DEFAULT FALSE
);

CREATE TABLE exif_metadata (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    image_id        INT NOT NULL,
    date_taken      DATETIME,
    camera_make     VARCHAR(100),
    camera_model    VARCHAR(100),
    serial_number   VARCHAR(100),
    lens_model      VARCHAR(100),
    image_width     INT,
    image_height    INT,
    iso             INT,
    flash           VARCHAR(50),
    white_balance   VARCHAR(50),
    orientation     VARCHAR(50),
    software        VARCHAR(100),
    gps_latitude    DECIMAL(10, 7),
    gps_longitude   DECIMAL(10, 7),
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE TABLE ai_tags (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    image_id            INT NOT NULL,
    scene_type          VARCHAR(50),
    scene_confidence    FLOAT,
    people_count        INT,
    people_confidence   FLOAT,
    tags                JSON, 
    -- [{"tag": "tent", "confidence": 0.87}, ...]
    categories          JSON,
    model_name          VARCHAR(100),
    is_verified         BOOLEAN DEFAULT FALSE,
    tagged_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE TABLE quality_scores (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    image_id            INT NOT NULL,
    sharpness_score     FLOAT,
    exposure_score      FLOAT,
    overall_score       FLOAT,
    is_best_in_group    BOOLEAN DEFAULT FALSE,
    scored_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE TABLE duplicate_clusters (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    image_id            INT NOT NULL,
    cluster_id          INT,
    cluster_type        VARCHAR(50),
    similarity_score    FLOAT,
    is_representative   BOOLEAN DEFAULT FALSE,
    clustered_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE TABLE embeddings (
    id             INT PRIMARY KEY AUTO_INCREMENT,
  image_id       INT          NOT NULL,
  image_uid      VARCHAR(64)  NULL,
  embedding_path VARCHAR(512) NULL,
  vector_json    LONGTEXT     NULL,
  row_index      INT          NULL,
  model_name     VARCHAR(128) NULL,
  file_hash      VARCHAR(128) NULL,
  updated_at     DATETIME     NULL,
  FOREIGN KEY (image_id) REFERENCES images(id),
  UNIQUE KEY uq_image (image_id)
);

CREATE TABLE corrections (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    image_id        INT NOT NULL,
    field_name      VARCHAR(100),
    ai_value        TEXT,
    human_value     TEXT,
    reviewer        VARCHAR(100),
    corrected_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id)
);