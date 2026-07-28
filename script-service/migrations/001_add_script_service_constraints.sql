DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_section_target'
          AND conrelid = 'sections'::regclass
    ) THEN
        ALTER TABLE sections
        ADD CONSTRAINT ck_section_target
        CHECK (
            (
                section_type = 'STOCK'
                AND target_type = 'STOCK'
                AND stock_code IS NOT NULL
                AND industry_code IS NULL
            )
            OR (
                section_type = 'INDUSTRY'
                AND target_type = 'INDUSTRY'
                AND stock_code IS NULL
                AND industry_code IS NOT NULL
            )
            OR (
                section_type IN (
                    'OPENING',
                    'BRIDGE',
                    'CLOSING'
                )
                AND target_type = 'USER'
                AND stock_code IS NULL
                AND industry_code IS NULL
            )
        ) NOT VALID;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_script_section_order_positive'
          AND conrelid = 'script_sections'::regclass
    ) THEN
        ALTER TABLE script_sections
        ADD CONSTRAINT ck_script_section_order_positive
        CHECK (section_order >= 1) NOT VALID;
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sections_stock_reuse
ON sections (
    stock_code,
    period_start,
    period_end
)
WHERE section_type = 'STOCK';

CREATE UNIQUE INDEX IF NOT EXISTS uq_sections_industry_reuse
ON sections (
    industry_code,
    period_start,
    period_end
)
WHERE section_type = 'INDUSTRY';

ALTER TABLE sections
VALIDATE CONSTRAINT ck_section_target;

ALTER TABLE script_sections
VALIDATE CONSTRAINT ck_script_section_order_positive;
