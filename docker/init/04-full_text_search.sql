-- =============================================================================
-- Full-Text Search Configuration
-- =============================================================================

-- Add tsvector columns to master tables for FTS
ALTER TABLE issuer ADD COLUMN IF NOT EXISTS search_vector tsvector;
ALTER TABLE issue ADD COLUMN IF NOT EXISTS search_vector tsvector;
ALTER TABLE issue_attribute ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Create GIN indexes for fast FTS
CREATE INDEX IF NOT EXISTS idx_issuer_search ON issuer USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_issue_search ON issue USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_issue_attr_search ON issue_attribute USING GIN(search_vector);

-- Function to update issuer search vector
CREATE OR REPLACE FUNCTION update_issuer_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.issuer_name_1, '') || ' ' ||
        COALESCE(NEW.issuer_name_2, '') || ' ' ||
        COALESCE(NEW.issuer_name_3, '') || ' ' ||
        COALESCE(NEW.issuer_sort_key, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update issue search vector
CREATE OR REPLACE FUNCTION update_issue_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.issue_desc_1, '') || ' ' ||
        COALESCE(NEW.issue_desc_2, '') || ' ' ||
        COALESCE(NEW.issue_adl_1, '') || ' ' ||
        COALESCE(NEW.issue_adl_2, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to update issue_attribute search vector
CREATE OR REPLACE FUNCTION update_issue_attr_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.ticker_symbol, '') || ' ' ||
        COALESCE(NEW.underwriter, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
DROP TRIGGER IF EXISTS issuer_search_trigger ON issuer;
CREATE TRIGGER issuer_search_trigger
    BEFORE INSERT OR UPDATE ON issuer
    FOR EACH ROW EXECUTE FUNCTION update_issuer_search_vector();

DROP TRIGGER IF EXISTS issue_search_trigger ON issue;
CREATE TRIGGER issue_search_trigger
    BEFORE INSERT OR UPDATE ON issue
    FOR EACH ROW EXECUTE FUNCTION update_issue_search_vector();

DROP TRIGGER IF EXISTS issue_attr_search_trigger ON issue_attribute;
CREATE TRIGGER issue_attr_search_trigger
    BEFORE INSERT OR UPDATE ON issue_attribute
    FOR EACH ROW EXECUTE FUNCTION update_issue_attr_search_vector();

-- =============================================================================
-- Search Function for PostgREST RPC
-- =============================================================================

-- Unified search function that searches across all entities
CREATE OR REPLACE FUNCTION search_securities(search_query text)
RETURNS TABLE (
    cusip varchar(9),
    issuer_name text,
    issue_description text,
    ticker_symbol varchar(10),
    underwriter varchar(60),
    match_type text,
    rank real
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check)::varchar(9) AS cusip,
        TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3)) AS issuer_name,
        TRIM(CONCAT(iss.issue_desc_1, iss.issue_desc_2)) AS issue_description,
        ia.ticker_symbol,
        ia.underwriter,
        CASE
            WHEN isr.search_vector @@ plainto_tsquery('english', search_query) THEN 'issuer'
            WHEN iss.search_vector @@ plainto_tsquery('english', search_query) THEN 'issue'
            WHEN ia.search_vector @@ plainto_tsquery('english', search_query) THEN 'attribute'
        END AS match_type,
        GREATEST(
            ts_rank(isr.search_vector, plainto_tsquery('english', search_query)),
            ts_rank(iss.search_vector, plainto_tsquery('english', search_query)),
            COALESCE(ts_rank(ia.search_vector, plainto_tsquery('english', search_query)), 0)
        ) AS rank
    FROM issue iss
    INNER JOIN issuer isr ON iss.issuer_num = isr.issuer_num
    LEFT JOIN issue_attribute ia ON iss.issuer_num = ia.issuer_num
                                 AND iss.issue_num = ia.issue_num
    WHERE isr.search_vector @@ plainto_tsquery('english', search_query)
       OR iss.search_vector @@ plainto_tsquery('english', search_query)
       OR ia.search_vector @@ plainto_tsquery('english', search_query)
    ORDER BY rank DESC;
END;
$$ LANGUAGE plpgsql STABLE;
