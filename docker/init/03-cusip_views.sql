-- =============================================================================
-- CUSIP Database Views
-- =============================================================================

CREATE OR REPLACE VIEW v_issuer AS
SELECT
    i.issuer_num,
    i.issuer_check,
    TRIM(CONCAT(i.issuer_name_1, i.issuer_name_2, i.issuer_name_3)) AS issuer_name,
    TRIM(CONCAT(i.issuer_adl_1, i.issuer_adl_2, i.issuer_adl_3, i.issuer_adl_4)) AS issuer_additional_info,
    i.issuer_sort_key,
    i.issuer_type,
    rt.description AS issuer_type_desc,
    i.issuer_status,
    rs.description AS issuer_status_desc,
    i.issuer_del_date,
    i.issuer_transaction,
    rx.description AS issuer_transaction_desc,
    i.issuer_state_code,
    i.issuer_update_date
FROM issuer i
LEFT JOIN ref_issuer_type rt ON i.issuer_type = rt.code
LEFT JOIN ref_issuer_status rs ON i.issuer_status = rs.code
LEFT JOIN ref_issuer_transaction rx ON i.issuer_transaction = rx.code;

CREATE OR REPLACE VIEW v_issue AS
SELECT
    i.issuer_num,
    i.issue_num,
    CONCAT(i.issuer_num, i.issue_num, i.issue_check) AS cusip,
    i.issue_check,
    TRIM(CONCAT(i.issue_desc_1, i.issue_desc_2)) AS issue_description,
    TRIM(CONCAT(i.issue_adl_1, i.issue_adl_2, i.issue_adl_3, i.issue_adl_4)) AS issue_additional_info,
    i.issue_status,
    rs.description AS issue_status_desc,
    i.dated_date,
    i.maturity_date,
    i.partial_maturity,
    i.rate,
    i.govt_stimulus_program,
    rg.description AS govt_stimulus_program_desc,
    i.issue_transaction,
    rx.description AS issue_transaction_desc,
    i.issue_update_date
FROM issue i
LEFT JOIN ref_issue_status rs ON i.issue_status = rs.code
LEFT JOIN ref_issue_transaction rx ON i.issue_transaction = rx.code
LEFT JOIN ref_govt_stimulus_program rg ON i.govt_stimulus_program = rg.code;

CREATE OR REPLACE VIEW v_issue_attribute AS
SELECT
    ia.issuer_num,
    ia.issue_num,
    CONCAT(ia.issuer_num, ia.issue_num) AS cusip_base,
    ia.alternative_min_tax,
    ia.bank_q,
    ia.callable,
    ia.activity_date,
    ia.first_coupon_date,
    ia.init_pub_off,
    ia.payment_frequency,
    rpf.description AS payment_frequency_desc,
    ia.currency_code,
    ia.domicile_code,
    ia.underwriter,
    ia.us_cfi_code,
    ia.closing_date,
    ia.ticker_symbol,
    ia.iso_cfi,
    ia.depos_eligible,
    ia.pre_refund,
    ia.refundable,
    ia.remarketed,
    ia.sinking_fund,
    ia.taxable,
    ia.form,
    ia.enhancements,
    ia.fund_distrb_policy,
    ia.fund_inv_policy,
    ia.fund_type,
    ia.guarantee,
    ia.income_type,
    ia.insured_by,
    ia.ownership_restr,
    ia.payment_status,
    ia.preferred_type,
    ia.putable,
    ia.rate_type,
    ia.redemption,
    ia.source_doc,
    ia.sponsoring,
    ia.voting_rights,
    ia.warrant_assets,
    ia.warrant_status,
    ia.warrant_type,
    ia.where_traded,
    ia.auditor,
    ia.paying_agent,
    ia.tender_agent,
    ia.xfer_agent,
    ia.bond_counsel,
    ia.financial_advisor,
    ia.municipal_sale_date,
    ia.sale_type,
    rst.description AS sale_type_desc,
    ia.offering_amount,
    ia.offering_amount_code,
    roa.description AS offering_amount_code_desc,
    CASE ia.offering_amount_code
        WHEN 'K' THEN ia.offering_amount * 1000
        WHEN 'M' THEN ia.offering_amount * 1000000
        WHEN 'B' THEN ia.offering_amount * 1000000000
        ELSE ia.offering_amount
    END AS offering_amount_full
FROM issue_attribute ia
LEFT JOIN ref_payment_frequency rpf ON ia.payment_frequency = rpf.code
LEFT JOIN ref_sale_type rst ON ia.sale_type = rst.code
LEFT JOIN ref_offering_amount_code roa ON ia.offering_amount_code = roa.code;

CREATE OR REPLACE VIEW v_security AS
SELECT
    CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check) AS cusip,
    iss.issuer_num,
    iss.issue_num,
    iss.issue_check,
    TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3)) AS issuer_name,
    isr.issuer_type,
    rit.description AS issuer_type_desc,
    isr.issuer_status,
    ris.description AS issuer_status_desc,
    isr.issuer_state_code,
    TRIM(CONCAT(iss.issue_desc_1, iss.issue_desc_2)) AS issue_description,
    TRIM(CONCAT(iss.issue_adl_1, iss.issue_adl_2, iss.issue_adl_3, iss.issue_adl_4)) AS issue_additional_info,
    iss.issue_status,
    rss.description AS issue_status_desc,
    iss.dated_date,
    iss.maturity_date,
    iss.rate,
    iss.govt_stimulus_program,
    rgs.description AS govt_stimulus_program_desc,
    ia.ticker_symbol,
    ia.currency_code,
    ia.domicile_code,
    ia.us_cfi_code,
    ia.iso_cfi,
    ia.payment_frequency,
    rpf.description AS payment_frequency_desc,
    ia.callable,
    ia.putable,
    ia.sinking_fund,
    ia.taxable,
    ia.alternative_min_tax,
    ia.bank_q,
    ia.depos_eligible,
    ia.form,
    ia.guarantee,
    ia.rate_type,
    ia.redemption,
    ia.where_traded,
    ia.underwriter,
    ia.offering_amount,
    ia.offering_amount_code,
    CASE ia.offering_amount_code
        WHEN 'K' THEN ia.offering_amount * 1000
        WHEN 'M' THEN ia.offering_amount * 1000000
        WHEN 'B' THEN ia.offering_amount * 1000000000
        ELSE ia.offering_amount
    END AS offering_amount_full,
    ia.activity_date,
    ia.first_coupon_date,
    ia.closing_date,
    ia.municipal_sale_date,
    iss.issue_update_date
FROM issue iss
INNER JOIN issuer isr ON iss.issuer_num = isr.issuer_num
LEFT JOIN issue_attribute ia ON iss.issuer_num = ia.issuer_num
                             AND iss.issue_num = ia.issue_num
LEFT JOIN ref_issuer_type rit ON isr.issuer_type = rit.code
LEFT JOIN ref_issuer_status ris ON isr.issuer_status = ris.code
LEFT JOIN ref_issue_status rss ON iss.issue_status = rss.code
LEFT JOIN ref_govt_stimulus_program rgs ON iss.govt_stimulus_program = rgs.code
LEFT JOIN ref_payment_frequency rpf ON ia.payment_frequency = rpf.code;

CREATE OR REPLACE VIEW v_security_summary AS
SELECT
    CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check) AS cusip,
    TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3)) AS issuer_name,
    TRIM(CONCAT(iss.issue_desc_1, iss.issue_desc_2)) AS issue_description,
    ia.ticker_symbol,
    rit.description AS issuer_type,
    rss.description AS issue_status,
    iss.rate,
    iss.dated_date,
    iss.maturity_date,
    ia.currency_code,
    ia.where_traded
FROM issue iss
INNER JOIN issuer isr ON iss.issuer_num = isr.issuer_num
LEFT JOIN issue_attribute ia ON iss.issuer_num = ia.issuer_num
                             AND iss.issue_num = ia.issue_num
LEFT JOIN ref_issuer_type rit ON isr.issuer_type = rit.code
LEFT JOIN ref_issue_status rss ON iss.issue_status = rss.code;
