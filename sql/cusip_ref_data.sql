-- =============================================================================
-- CUSIP Reference Data
-- =============================================================================

INSERT INTO ref_issuer_type (code, description) VALUES
    ('C', 'Corporate Issuer'),
    ('M', 'Municipal Issuer'),
    ('G', 'U.S. Government Issuer'),
    ('S', 'Sovereign Issuer');

INSERT INTO ref_issuer_status (code, description) VALUES
    ('A', 'Active'),
    ('D', 'Suspend');

INSERT INTO ref_issuer_transaction (code, description) VALUES
    ('A', 'New Issuer'),
    ('B', 'New Issuer - Company Name Change'),
    ('L', 'Description Correction Not Requiring New Number'),
    ('N', 'Company Name Change Not Requiring New Number'),
    ('R', 'Suspend Drop: Merged, Name Changed, Assets Acquired, Re-Domiciled'),
    ('T', 'Suspend Drop: Bankrupt, Liquidated, Authority Discontinued'),
    ('W', 'Immediate Drop: Registration Withdrawn');

INSERT INTO ref_issue_status (code, description) VALUES
    ('A', 'Active'),
    ('T', 'Temporary Add - Rate/Maturity Not Final'),
    ('D', 'Suspend'),
    ('X', 'Issue Presumed Inactive'),
    ('Z', 'Issue Matured');

INSERT INTO ref_issue_transaction (code, description) VALUES
    ('A', 'New Issue'),
    ('D', 'Tentative Add - Coupon Rate Not Yet Available'),
    ('L', 'Description Correction Not Requiring New Number'),
    ('M', 'Tentative Add Now Permanent'),
    ('S', 'Suspend Drop: Called, Expired, Exchanged, Redeemed'),
    ('W', 'Immediate Drop: Registration Withdrawn');

INSERT INTO ref_govt_stimulus_program (code, description) VALUES
    ('A', 'Qualified Zone Academy Bonds (QZAB)'),
    ('B', 'Build America Bonds'),
    ('C', 'Recovery Zone Facility Bonds'),
    ('D', 'New Clean Renewable Energy Bonds (New CREB)'),
    ('E', 'Qualified Energy Conservation Bonds'),
    ('F', 'FDIC TLGP'),
    ('G', 'Tribal Economic Development Bonds'),
    ('H', 'New Issue Bond Program NIBP - US Treasury HFA'),
    ('M', 'Municipal Liquidity Facility'),
    ('N', 'N/A'),
    ('P', 'TARP'),
    ('Q', 'Qualified School Construction Bonds'),
    ('R', 'Recovery Zone Economic Development Bonds'),
    ('T', 'TALF'),
    ('V', 'Clean Renewable Energy Bonds (CREB)');

INSERT INTO ref_payment_frequency (code, description) VALUES
    ('1', 'Daily'),
    ('2', 'Weekly'),
    ('3', 'Monthly'),
    ('4', 'Quarterly'),
    ('5', 'Semi-Annually'),
    ('6', 'Annually'),
    ('7', 'At Maturity'),
    ('8', 'Zero Coupon / Capital Appreciation Bonds'),
    ('9', 'Semi-Monthly'),
    ('Z', 'Not Applicable');

INSERT INTO ref_sale_type (code, description) VALUES
    ('C', 'Competitive'),
    ('G', 'Negotiated');

INSERT INTO ref_offering_amount_code (code, description) VALUES
    ('K', 'Thousands'),
    ('M', 'Millions'),
    ('B', 'Billions');
