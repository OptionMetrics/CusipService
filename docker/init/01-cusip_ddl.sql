-- =============================================================================
-- CUSIP Database DDL for PostgreSQL
-- =============================================================================

-- =============================================================================
-- REFERENCE TABLES
-- =============================================================================

CREATE TABLE ref_issuer_type (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

CREATE TABLE ref_issuer_status (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

CREATE TABLE ref_issuer_transaction (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

CREATE TABLE ref_issue_status (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

CREATE TABLE ref_issue_transaction (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

CREATE TABLE ref_govt_stimulus_program (
    code        VARCHAR(10) PRIMARY KEY,
    description VARCHAR(100) NOT NULL
);

CREATE TABLE ref_payment_frequency (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

CREATE TABLE ref_sale_type (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

CREATE TABLE ref_offering_amount_code (
    code        VARCHAR(1) PRIMARY KEY,
    description VARCHAR(50) NOT NULL
);

-- =============================================================================
-- MASTER TABLES
-- =============================================================================

CREATE TABLE issuer (
    issuer_num          VARCHAR(6) NOT NULL,
    issuer_check        VARCHAR(1),
    issuer_name_1       VARCHAR(30),
    issuer_name_2       VARCHAR(30),
    issuer_name_3       VARCHAR(30),
    issuer_adl_1        VARCHAR(30),
    issuer_adl_2        VARCHAR(30),
    issuer_adl_3        VARCHAR(30),
    issuer_adl_4        VARCHAR(30),
    issuer_sort_key     VARCHAR(30),
    issuer_type         VARCHAR(1),
    issuer_status       VARCHAR(1),
    issuer_del_date     DATE,
    issuer_transaction  VARCHAR(1),
    issuer_state_code   VARCHAR(2),
    issuer_update_date  DATE,

    CONSTRAINT pk_issuer PRIMARY KEY (issuer_num),
    CONSTRAINT fk_issuer_type FOREIGN KEY (issuer_type)
        REFERENCES ref_issuer_type(code),
    CONSTRAINT fk_issuer_status FOREIGN KEY (issuer_status)
        REFERENCES ref_issuer_status(code),
    CONSTRAINT fk_issuer_transaction FOREIGN KEY (issuer_transaction)
        REFERENCES ref_issuer_transaction(code)
);

CREATE TABLE issue (
    issuer_num              VARCHAR(6) NOT NULL,
    issue_num               VARCHAR(2) NOT NULL,
    issue_check             VARCHAR(1),
    issue_desc_1            VARCHAR(30),
    issue_desc_2            VARCHAR(30),
    issue_adl_1             VARCHAR(30),
    issue_adl_2             VARCHAR(30),
    issue_adl_3             VARCHAR(30),
    issue_adl_4             VARCHAR(30),
    issue_status            VARCHAR(1),
    dated_date              DATE,
    maturity_date           DATE,
    partial_maturity        INTEGER,
    rate                    DECIMAL(6,3),
    govt_stimulus_program   VARCHAR(10),
    issue_transaction       VARCHAR(1),
    issue_update_date       DATE,

    CONSTRAINT pk_issue PRIMARY KEY (issuer_num, issue_num),
    CONSTRAINT fk_issue_issuer FOREIGN KEY (issuer_num)
        REFERENCES issuer(issuer_num),
    CONSTRAINT fk_issue_status FOREIGN KEY (issue_status)
        REFERENCES ref_issue_status(code),
    CONSTRAINT fk_issue_transaction FOREIGN KEY (issue_transaction)
        REFERENCES ref_issue_transaction(code),
    CONSTRAINT fk_issue_govt_stimulus FOREIGN KEY (govt_stimulus_program)
        REFERENCES ref_govt_stimulus_program(code)
);

CREATE TABLE issue_attribute (
    issuer_num              VARCHAR(6) NOT NULL,
    issue_num               VARCHAR(2) NOT NULL,
    alternative_min_tax     VARCHAR(1),
    bank_q                  VARCHAR(1),
    callable                VARCHAR(1),
    activity_date           DATE,
    first_coupon_date       DATE,
    init_pub_off            VARCHAR(1),
    payment_frequency       VARCHAR(1),
    currency_code           VARCHAR(3),
    domicile_code           VARCHAR(2),
    underwriter             VARCHAR(60),
    us_cfi_code             VARCHAR(6),
    closing_date            DATE,
    ticker_symbol           VARCHAR(10),
    iso_cfi                 VARCHAR(6),
    depos_eligible          VARCHAR(1),
    pre_refund              VARCHAR(1),
    refundable              VARCHAR(1),
    remarketed              VARCHAR(1),
    sinking_fund            VARCHAR(1),
    taxable                 VARCHAR(1),
    form                    VARCHAR(50),
    enhancements            VARCHAR(50),
    fund_distrb_policy      VARCHAR(50),
    fund_inv_policy         VARCHAR(50),
    fund_type               VARCHAR(50),
    guarantee               VARCHAR(50),
    income_type             VARCHAR(50),
    insured_by              VARCHAR(50),
    ownership_restr         VARCHAR(50),
    payment_status          VARCHAR(50),
    preferred_type          VARCHAR(50),
    putable                 VARCHAR(50),
    rate_type               VARCHAR(50),
    redemption              VARCHAR(50),
    source_doc              VARCHAR(50),
    sponsoring              VARCHAR(50),
    voting_rights           VARCHAR(50),
    warrant_assets          VARCHAR(50),
    warrant_status          VARCHAR(50),
    warrant_type            VARCHAR(50),
    where_traded            VARCHAR(50),
    auditor                 VARCHAR(60),
    paying_agent            VARCHAR(60),
    tender_agent            VARCHAR(60),
    xfer_agent              VARCHAR(60),
    bond_counsel            VARCHAR(60),
    financial_advisor       VARCHAR(60),
    municipal_sale_date     DATE,
    sale_type               VARCHAR(1),
    offering_amount         DECIMAL(5,1),
    offering_amount_code    VARCHAR(1),

    CONSTRAINT pk_issue_attribute PRIMARY KEY (issuer_num, issue_num),
    CONSTRAINT fk_issue_attr_issue FOREIGN KEY (issuer_num, issue_num)
        REFERENCES issue(issuer_num, issue_num),
    CONSTRAINT fk_issue_attr_payment_freq FOREIGN KEY (payment_frequency)
        REFERENCES ref_payment_frequency(code),
    CONSTRAINT fk_issue_attr_sale_type FOREIGN KEY (sale_type)
        REFERENCES ref_sale_type(code),
    CONSTRAINT fk_issue_attr_offering_code FOREIGN KEY (offering_amount_code)
        REFERENCES ref_offering_amount_code(code)
);

-- =============================================================================
-- STAGING TABLES (no constraints, for bulk loading)
-- =============================================================================

CREATE TABLE stg_issuer (
    issuer_num          VARCHAR(6),
    issuer_check        VARCHAR(1),
    issuer_name_1       VARCHAR(30),
    issuer_name_2       VARCHAR(30),
    issuer_name_3       VARCHAR(30),
    issuer_adl_1        VARCHAR(30),
    issuer_adl_2        VARCHAR(30),
    issuer_adl_3        VARCHAR(30),
    issuer_adl_4        VARCHAR(30),
    issuer_sort_key     VARCHAR(30),
    issuer_type         VARCHAR(1),
    issuer_status       VARCHAR(1),
    issuer_del_date     DATE,
    issuer_transaction  VARCHAR(1),
    issuer_state_code   VARCHAR(2),
    issuer_update_date  DATE
);

CREATE TABLE stg_issue (
    issuer_num              VARCHAR(6),
    issue_num               VARCHAR(2),
    issue_check             VARCHAR(1),
    issue_desc_1            VARCHAR(30),
    issue_desc_2            VARCHAR(30),
    issue_adl_1             VARCHAR(30),
    issue_adl_2             VARCHAR(30),
    issue_adl_3             VARCHAR(30),
    issue_adl_4             VARCHAR(30),
    issue_status            VARCHAR(1),
    dated_date              DATE,
    maturity_date           DATE,
    partial_maturity        INTEGER,
    rate                    DECIMAL(6,3),
    govt_stimulus_program   VARCHAR(10),
    issue_transaction       VARCHAR(1),
    issue_update_date       DATE
);

CREATE TABLE stg_issue_attribute (
    issuer_num              VARCHAR(6),
    issue_num               VARCHAR(2),
    alternative_min_tax     VARCHAR(1),
    bank_q                  VARCHAR(1),
    callable                VARCHAR(1),
    activity_date           DATE,
    first_coupon_date       DATE,
    init_pub_off            VARCHAR(1),
    payment_frequency       VARCHAR(1),
    currency_code           VARCHAR(3),
    domicile_code           VARCHAR(2),
    underwriter             VARCHAR(60),
    us_cfi_code             VARCHAR(6),
    closing_date            DATE,
    ticker_symbol           VARCHAR(10),
    iso_cfi                 VARCHAR(6),
    depos_eligible          VARCHAR(1),
    pre_refund              VARCHAR(1),
    refundable              VARCHAR(1),
    remarketed              VARCHAR(1),
    sinking_fund            VARCHAR(1),
    taxable                 VARCHAR(1),
    form                    VARCHAR(50),
    enhancements            VARCHAR(50),
    fund_distrb_policy      VARCHAR(50),
    fund_inv_policy         VARCHAR(50),
    fund_type               VARCHAR(50),
    guarantee               VARCHAR(50),
    income_type             VARCHAR(50),
    insured_by              VARCHAR(50),
    ownership_restr         VARCHAR(50),
    payment_status          VARCHAR(50),
    preferred_type          VARCHAR(50),
    putable                 VARCHAR(50),
    rate_type               VARCHAR(50),
    redemption              VARCHAR(50),
    source_doc              VARCHAR(50),
    sponsoring              VARCHAR(50),
    voting_rights           VARCHAR(50),
    warrant_assets          VARCHAR(50),
    warrant_status          VARCHAR(50),
    warrant_type            VARCHAR(50),
    where_traded            VARCHAR(50),
    auditor                 VARCHAR(60),
    paying_agent            VARCHAR(60),
    tender_agent            VARCHAR(60),
    xfer_agent              VARCHAR(60),
    bond_counsel            VARCHAR(60),
    financial_advisor       VARCHAR(60),
    municipal_sale_date     DATE,
    sale_type               VARCHAR(1),
    offering_amount         DECIMAL(5,1),
    offering_amount_code    VARCHAR(1)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX idx_issuer_status ON issuer(issuer_status);
CREATE INDEX idx_issuer_type ON issuer(issuer_type);
CREATE INDEX idx_issuer_state ON issuer(issuer_state_code);

CREATE INDEX idx_issue_status ON issue(issue_status);
CREATE INDEX idx_issue_maturity ON issue(maturity_date);
CREATE INDEX idx_issue_dated ON issue(dated_date);

CREATE INDEX idx_issue_attr_currency ON issue_attribute(currency_code);
CREATE INDEX idx_issue_attr_domicile ON issue_attribute(domicile_code);
CREATE INDEX idx_issue_attr_ticker ON issue_attribute(ticker_symbol);
