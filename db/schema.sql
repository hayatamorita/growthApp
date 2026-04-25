CREATE TABLE IF NOT EXISTS children (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    birthday DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS growth_records (
    id SERIAL PRIMARY KEY,
    child_id INTEGER NOT NULL REFERENCES children(id) ON DELETE CASCADE,
    record_date DATE NOT NULL,
    height_cm NUMERIC,
    weight_kg NUMERIC,
    memo TEXT,
    image_data BYTEA,
    image_mime_type TEXT,
    image_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_growth_records_child_id
    ON growth_records (child_id);

CREATE INDEX IF NOT EXISTS idx_growth_records_record_date
    ON growth_records (record_date);
