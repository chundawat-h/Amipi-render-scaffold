-- AMIPI Rendering Standardization — PostgreSQL schema
-- Run this directly, or let SQLAlchemy/Alembic manage it — this file is the
-- readable source of truth for the data model either way.

CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    sku             VARCHAR(64) UNIQUE NOT NULL,       -- Style No. from ERP
    stone_count     INTEGER,
    stone_size_ct   NUMERIC(6,3),                       -- carat weight, e.g. 1.250
    dimensions_mm   VARCHAR(64),                        -- e.g. "13.90 x 9.80 x 6.65"
    ring_size       VARCHAR(16),                        -- e.g. "US-6.5", nullable (not all products are rings)
    metal_type      VARCHAR(32),                        -- internal_only — never selected into technical-image queries
    category        VARCHAR(64),                        -- ring / earring / bracelet / necklace ...
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Versioned rendering guideline — this IS the documented standard, made queryable
-- so the render engine reads config instead of a human reading a PDF.
CREATE TABLE IF NOT EXISTS render_templates (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(64) NOT NULL,               -- e.g. "AMIPI Standard v1"
    version         INTEGER NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT false,
    config          JSONB NOT NULL,                      -- camera angles, lighting rig, background, output sizes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER REFERENCES products(id) ON DELETE SET NULL,
    input_type      VARCHAR(16) NOT NULL CHECK (input_type IN ('cad', 'stl', 'obj', 'jpeg')),
    input_path      TEXT NOT NULL,
    pipeline        VARCHAR(16) NOT NULL CHECK (pipeline IN ('render_3d', 'normalize_2d')),
    template_id     INTEGER REFERENCES render_templates(id),
    status          VARCHAR(16) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    error_message   TEXT,
    output_paths    JSONB,                               -- {"hero": "...", "thumbnail": "...", "technical": "..."}
    requested_by    VARCHAR(64),                          -- team/user, for audit trail — not heavy auth
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_render_jobs_product ON render_jobs(product_id);
CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);

-- Seed the first draft of the rendering guideline (adjust after review with AMIPI).
INSERT INTO render_templates (name, version, is_active, config)
VALUES (
    'AMIPI Standard',
    1,
    true,
    '{
        "camera": {
            "views": ["hero_3quarter", "front", "top"],
            "focal_length_mm": 85,
            "distance_factor": 2.2
        },
        "lighting": {
            "type": "studio_hdri",
            "hdri": "studio_soft_01",
            "key_intensity": 1.0,
            "fill_intensity": 0.4,
            "rim_intensity": 0.6
        },
        "background": {
            "type": "gradient",
            "color_top": "#FFFFFF",
            "color_bottom": "#F2EFEA"
        },
        "output_sizes": {
            "hero": [2000, 2000],
            "thumbnail": [800, 800],
            "technical": [1600, 1600]
        },
        "watermark": {
            "logo_path": "assets/amipi_logo.png",
            "position": "bottom_right",
            "margin_px": 24
        }
    }'::jsonb
)
ON CONFLICT (name, version) DO NOTHING;
