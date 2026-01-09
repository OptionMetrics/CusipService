-- =============================================================================
-- PostgREST Roles and Permissions
-- =============================================================================

-- Authenticator role (used by PostgREST to connect)
CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'changeme';

-- Anonymous role for unauthenticated access (read-only on views)
CREATE ROLE web_anon NOLOGIN;

-- Grant web_anon to authenticator so it can switch to this role
GRANT web_anon TO authenticator;

-- Grant read access on schema to web_anon
GRANT USAGE ON SCHEMA public TO web_anon;

-- Grant SELECT on all views
GRANT SELECT ON v_issuer TO web_anon;
GRANT SELECT ON v_issue TO web_anon;
GRANT SELECT ON v_issue_attribute TO web_anon;
GRANT SELECT ON v_security TO web_anon;
GRANT SELECT ON v_security_summary TO web_anon;

-- Grant access to reference tables (useful for lookups)
GRANT SELECT ON ref_issuer_type TO web_anon;
GRANT SELECT ON ref_issuer_status TO web_anon;
GRANT SELECT ON ref_issuer_transaction TO web_anon;
GRANT SELECT ON ref_issue_status TO web_anon;
GRANT SELECT ON ref_issue_transaction TO web_anon;
GRANT SELECT ON ref_govt_stimulus_program TO web_anon;
GRANT SELECT ON ref_payment_frequency TO web_anon;
GRANT SELECT ON ref_sale_type TO web_anon;
GRANT SELECT ON ref_offering_amount_code TO web_anon;

-- Grant execute permission on search function
GRANT EXECUTE ON FUNCTION search_securities(text) TO web_anon;
