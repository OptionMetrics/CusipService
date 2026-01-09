"""Initial schema - reference tables, master tables, staging tables, views, FTS.

Revision ID: 001
Revises:
Create Date: 2024-01-09

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==========================================================================
    # REFERENCE TABLES
    # ==========================================================================
    op.execute("""
        CREATE TABLE ref_issuer_type (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_issuer_status (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_issuer_transaction (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(100) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_issue_status (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_issue_transaction (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(100) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_govt_stimulus_program (
            code        VARCHAR(10) PRIMARY KEY,
            description VARCHAR(100) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_payment_frequency (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_sale_type (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE ref_offering_amount_code (
            code        VARCHAR(1) PRIMARY KEY,
            description VARCHAR(50) NOT NULL
        )
    """)

    # ==========================================================================
    # REFERENCE DATA
    # ==========================================================================
    op.execute("""
        INSERT INTO ref_issuer_type (code, description) VALUES
            ('C', 'Corporate Issuer'),
            ('M', 'Municipal Issuer'),
            ('G', 'U.S. Government Issuer'),
            ('S', 'Sovereign Issuer')
    """)

    op.execute("""
        INSERT INTO ref_issuer_status (code, description) VALUES
            ('A', 'Active'),
            ('D', 'Suspend')
    """)

    op.execute("""
        INSERT INTO ref_issuer_transaction (code, description) VALUES
            ('A', 'New Issuer'),
            ('B', 'New Issuer - Company Name Change'),
            ('L', 'Description Correction Not Requiring New Number'),
            ('N', 'Company Name Change Not Requiring New Number'),
            ('R', 'Suspend Drop: Merged, Name Changed, Assets Acquired, Re-Domiciled'),
            ('T', 'Suspend Drop: Bankrupt, Liquidated, Authority Discontinued'),
            ('W', 'Immediate Drop: Registration Withdrawn')
    """)

    op.execute("""
        INSERT INTO ref_issue_status (code, description) VALUES
            ('A', 'Active'),
            ('T', 'Temporary Add - Rate/Maturity Not Final'),
            ('D', 'Suspend'),
            ('X', 'Issue Presumed Inactive'),
            ('Z', 'Issue Matured')
    """)

    op.execute("""
        INSERT INTO ref_issue_transaction (code, description) VALUES
            ('A', 'New Issue'),
            ('D', 'Tentative Add - Coupon Rate Not Yet Available'),
            ('L', 'Description Correction Not Requiring New Number'),
            ('M', 'Tentative Add Now Permanent'),
            ('S', 'Suspend Drop: Called, Expired, Exchanged, Redeemed'),
            ('W', 'Immediate Drop: Registration Withdrawn')
    """)

    op.execute("""
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
            ('V', 'Clean Renewable Energy Bonds (CREB)')
    """)

    op.execute("""
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
            ('Z', 'Not Applicable')
    """)

    op.execute("""
        INSERT INTO ref_sale_type (code, description) VALUES
            ('C', 'Competitive'),
            ('G', 'Negotiated')
    """)

    op.execute("""
        INSERT INTO ref_offering_amount_code (code, description) VALUES
            ('K', 'Thousands'),
            ('M', 'Millions'),
            ('B', 'Billions')
    """)

    # ==========================================================================
    # MASTER TABLES
    # ==========================================================================
    op.execute("""
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
            search_vector       tsvector,

            CONSTRAINT pk_issuer PRIMARY KEY (issuer_num),
            CONSTRAINT fk_issuer_type FOREIGN KEY (issuer_type)
                REFERENCES ref_issuer_type(code),
            CONSTRAINT fk_issuer_status FOREIGN KEY (issuer_status)
                REFERENCES ref_issuer_status(code),
            CONSTRAINT fk_issuer_transaction FOREIGN KEY (issuer_transaction)
                REFERENCES ref_issuer_transaction(code)
        )
    """)

    op.execute("""
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
            search_vector           tsvector,

            CONSTRAINT pk_issue PRIMARY KEY (issuer_num, issue_num),
            CONSTRAINT fk_issue_issuer FOREIGN KEY (issuer_num)
                REFERENCES issuer(issuer_num),
            CONSTRAINT fk_issue_status FOREIGN KEY (issue_status)
                REFERENCES ref_issue_status(code),
            CONSTRAINT fk_issue_transaction FOREIGN KEY (issue_transaction)
                REFERENCES ref_issue_transaction(code),
            CONSTRAINT fk_issue_govt_stimulus FOREIGN KEY (govt_stimulus_program)
                REFERENCES ref_govt_stimulus_program(code)
        )
    """)

    op.execute("""
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
            search_vector           tsvector,

            CONSTRAINT pk_issue_attribute PRIMARY KEY (issuer_num, issue_num),
            CONSTRAINT fk_issue_attr_issue FOREIGN KEY (issuer_num, issue_num)
                REFERENCES issue(issuer_num, issue_num),
            CONSTRAINT fk_issue_attr_payment_freq FOREIGN KEY (payment_frequency)
                REFERENCES ref_payment_frequency(code),
            CONSTRAINT fk_issue_attr_sale_type FOREIGN KEY (sale_type)
                REFERENCES ref_sale_type(code),
            CONSTRAINT fk_issue_attr_offering_code FOREIGN KEY (offering_amount_code)
                REFERENCES ref_offering_amount_code(code)
        )
    """)

    # ==========================================================================
    # STAGING TABLES
    # ==========================================================================
    op.execute("""
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
        )
    """)

    op.execute("""
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
        )
    """)

    op.execute("""
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
        )
    """)

    # ==========================================================================
    # INDEXES
    # ==========================================================================
    op.execute("CREATE INDEX idx_issuer_status ON issuer(issuer_status)")
    op.execute("CREATE INDEX idx_issuer_type ON issuer(issuer_type)")
    op.execute("CREATE INDEX idx_issuer_state ON issuer(issuer_state_code)")
    op.execute("CREATE INDEX idx_issuer_search ON issuer USING GIN(search_vector)")

    op.execute("CREATE INDEX idx_issue_status ON issue(issue_status)")
    op.execute("CREATE INDEX idx_issue_maturity ON issue(maturity_date)")
    op.execute("CREATE INDEX idx_issue_dated ON issue(dated_date)")
    op.execute("CREATE INDEX idx_issue_search ON issue USING GIN(search_vector)")

    op.execute("CREATE INDEX idx_issue_attr_currency ON issue_attribute(currency_code)")
    op.execute("CREATE INDEX idx_issue_attr_domicile ON issue_attribute(domicile_code)")
    op.execute("CREATE INDEX idx_issue_attr_ticker ON issue_attribute(ticker_symbol)")
    op.execute(
        "CREATE INDEX idx_issue_attr_search ON issue_attribute USING GIN(search_vector)"
    )

    # ==========================================================================
    # FULL-TEXT SEARCH TRIGGERS
    # ==========================================================================
    op.execute("""
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
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
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
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_issue_attr_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                COALESCE(NEW.ticker_symbol, '') || ' ' ||
                COALESCE(NEW.underwriter, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER issuer_search_trigger
            BEFORE INSERT OR UPDATE ON issuer
            FOR EACH ROW EXECUTE FUNCTION update_issuer_search_vector()
    """)

    op.execute("""
        CREATE TRIGGER issue_search_trigger
            BEFORE INSERT OR UPDATE ON issue
            FOR EACH ROW EXECUTE FUNCTION update_issue_search_vector()
    """)

    op.execute("""
        CREATE TRIGGER issue_attr_search_trigger
            BEFORE INSERT OR UPDATE ON issue_attribute
            FOR EACH ROW EXECUTE FUNCTION update_issue_attr_search_vector()
    """)

    # ==========================================================================
    # SEARCH FUNCTION
    # ==========================================================================
    op.execute("""
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
                CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check)::varchar(9),
                TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3)),
                TRIM(CONCAT(iss.issue_desc_1, iss.issue_desc_2)),
                ia.ticker_symbol,
                ia.underwriter,
                CASE
                    WHEN isr.search_vector @@ plainto_tsquery('english', search_query)
                        THEN 'issuer'
                    WHEN iss.search_vector @@ plainto_tsquery('english', search_query)
                        THEN 'issue'
                    WHEN ia.search_vector @@ plainto_tsquery('english', search_query)
                        THEN 'attribute'
                END,
                GREATEST(
                    ts_rank(isr.search_vector, plainto_tsquery('english', search_query)),
                    ts_rank(iss.search_vector, plainto_tsquery('english', search_query)),
                    COALESCE(
                        ts_rank(ia.search_vector, plainto_tsquery('english', search_query)),
                        0
                    )
                )
            FROM issue iss
            INNER JOIN issuer isr ON iss.issuer_num = isr.issuer_num
            LEFT JOIN issue_attribute ia ON iss.issuer_num = ia.issuer_num
                                         AND iss.issue_num = ia.issue_num
            WHERE isr.search_vector @@ plainto_tsquery('english', search_query)
               OR iss.search_vector @@ plainto_tsquery('english', search_query)
               OR ia.search_vector @@ plainto_tsquery('english', search_query)
            ORDER BY rank DESC;
        END;
        $$ LANGUAGE plpgsql STABLE
    """)

    # ==========================================================================
    # VIEWS
    # ==========================================================================
    op.execute("""
        CREATE OR REPLACE VIEW v_issuer AS
        SELECT
            i.issuer_num,
            i.issuer_check,
            TRIM(CONCAT(i.issuer_name_1, i.issuer_name_2, i.issuer_name_3)) AS issuer_name,
            TRIM(CONCAT(i.issuer_adl_1, i.issuer_adl_2, i.issuer_adl_3, i.issuer_adl_4))
                AS issuer_additional_info,
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
        LEFT JOIN ref_issuer_transaction rx ON i.issuer_transaction = rx.code
    """)

    op.execute("""
        CREATE OR REPLACE VIEW v_issue AS
        SELECT
            i.issuer_num,
            i.issue_num,
            CONCAT(i.issuer_num, i.issue_num, i.issue_check) AS cusip,
            i.issue_check,
            TRIM(CONCAT(i.issue_desc_1, i.issue_desc_2)) AS issue_description,
            TRIM(CONCAT(i.issue_adl_1, i.issue_adl_2, i.issue_adl_3, i.issue_adl_4))
                AS issue_additional_info,
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
        LEFT JOIN ref_govt_stimulus_program rg ON i.govt_stimulus_program = rg.code
    """)

    op.execute("""
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
        LEFT JOIN ref_offering_amount_code roa ON ia.offering_amount_code = roa.code
    """)

    op.execute("""
        CREATE OR REPLACE VIEW v_security AS
        SELECT
            CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check) AS cusip,
            iss.issuer_num,
            iss.issue_num,
            iss.issue_check,
            TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3))
                AS issuer_name,
            isr.issuer_type,
            rit.description AS issuer_type_desc,
            isr.issuer_status,
            ris.description AS issuer_status_desc,
            isr.issuer_state_code,
            TRIM(CONCAT(iss.issue_desc_1, iss.issue_desc_2)) AS issue_description,
            TRIM(CONCAT(iss.issue_adl_1, iss.issue_adl_2, iss.issue_adl_3, iss.issue_adl_4))
                AS issue_additional_info,
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
        LEFT JOIN ref_payment_frequency rpf ON ia.payment_frequency = rpf.code
    """)

    op.execute("""
        CREATE OR REPLACE VIEW v_security_summary AS
        SELECT
            CONCAT(iss.issuer_num, iss.issue_num, iss.issue_check) AS cusip,
            TRIM(CONCAT(isr.issuer_name_1, isr.issuer_name_2, isr.issuer_name_3))
                AS issuer_name,
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
        LEFT JOIN ref_issue_status rss ON iss.issue_status = rss.code
    """)

    # ==========================================================================
    # POSTGREST ROLES
    # ==========================================================================
    op.execute("CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'changeme'")
    op.execute("CREATE ROLE web_anon NOLOGIN")
    op.execute("GRANT web_anon TO authenticator")
    op.execute("GRANT USAGE ON SCHEMA public TO web_anon")

    # Grant SELECT on views
    op.execute("GRANT SELECT ON v_issuer TO web_anon")
    op.execute("GRANT SELECT ON v_issue TO web_anon")
    op.execute("GRANT SELECT ON v_issue_attribute TO web_anon")
    op.execute("GRANT SELECT ON v_security TO web_anon")
    op.execute("GRANT SELECT ON v_security_summary TO web_anon")

    # Grant SELECT on reference tables
    op.execute("GRANT SELECT ON ref_issuer_type TO web_anon")
    op.execute("GRANT SELECT ON ref_issuer_status TO web_anon")
    op.execute("GRANT SELECT ON ref_issuer_transaction TO web_anon")
    op.execute("GRANT SELECT ON ref_issue_status TO web_anon")
    op.execute("GRANT SELECT ON ref_issue_transaction TO web_anon")
    op.execute("GRANT SELECT ON ref_govt_stimulus_program TO web_anon")
    op.execute("GRANT SELECT ON ref_payment_frequency TO web_anon")
    op.execute("GRANT SELECT ON ref_sale_type TO web_anon")
    op.execute("GRANT SELECT ON ref_offering_amount_code TO web_anon")

    # Grant EXECUTE on search function
    op.execute("GRANT EXECUTE ON FUNCTION search_securities(text) TO web_anon")


def downgrade() -> None:
    # Drop roles
    op.execute("DROP ROLE IF EXISTS web_anon")
    op.execute("DROP ROLE IF EXISTS authenticator")

    # Drop views
    op.execute("DROP VIEW IF EXISTS v_security_summary")
    op.execute("DROP VIEW IF EXISTS v_security")
    op.execute("DROP VIEW IF EXISTS v_issue_attribute")
    op.execute("DROP VIEW IF EXISTS v_issue")
    op.execute("DROP VIEW IF EXISTS v_issuer")

    # Drop search function
    op.execute("DROP FUNCTION IF EXISTS search_securities(text)")

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS issue_attr_search_trigger ON issue_attribute")
    op.execute("DROP TRIGGER IF EXISTS issue_search_trigger ON issue")
    op.execute("DROP TRIGGER IF EXISTS issuer_search_trigger ON issuer")

    # Drop trigger functions
    op.execute("DROP FUNCTION IF EXISTS update_issue_attr_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS update_issue_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS update_issuer_search_vector()")

    # Drop staging tables
    op.execute("DROP TABLE IF EXISTS stg_issue_attribute")
    op.execute("DROP TABLE IF EXISTS stg_issue")
    op.execute("DROP TABLE IF EXISTS stg_issuer")

    # Drop master tables (in reverse FK order)
    op.execute("DROP TABLE IF EXISTS issue_attribute")
    op.execute("DROP TABLE IF EXISTS issue")
    op.execute("DROP TABLE IF EXISTS issuer")

    # Drop reference tables
    op.execute("DROP TABLE IF EXISTS ref_offering_amount_code")
    op.execute("DROP TABLE IF EXISTS ref_sale_type")
    op.execute("DROP TABLE IF EXISTS ref_payment_frequency")
    op.execute("DROP TABLE IF EXISTS ref_govt_stimulus_program")
    op.execute("DROP TABLE IF EXISTS ref_issue_transaction")
    op.execute("DROP TABLE IF EXISTS ref_issue_status")
    op.execute("DROP TABLE IF EXISTS ref_issuer_transaction")
    op.execute("DROP TABLE IF EXISTS ref_issuer_status")
    op.execute("DROP TABLE IF EXISTS ref_issuer_type")
