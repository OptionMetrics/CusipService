"""
CUSIP File Loader

Loads CUSIP PIF files (Issuer, Issue, Issue Attributes) into PostgreSQL
with staging table + upsert pattern in a single transaction.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TextIO, TypedDict

import psycopg2
from psycopg2 import sql

# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class FileConfig(TypedDict):
    """Configuration for a CUSIP file type."""

    table: str
    staging_table: str
    pk_columns: list[str]
    columns: list[str]


class DbConfig(TypedDict):
    """Database connection configuration."""

    host: str
    port: int
    dbname: str
    user: str
    password: str


class LoadResult(TypedDict, total=False):
    """Result of loading a file."""

    file: str
    type: str
    rows_read: int
    rows_upserted: int
    status: str
    error: str


# =============================================================================
# FILE CONFIGURATION
# =============================================================================

FILE_CONFIG: dict[str, FileConfig] = {
    "issuer": {
        "table": "issuer",
        "staging_table": "stg_issuer",
        "pk_columns": ["issuer_num"],
        "columns": [
            "issuer_num",
            "issuer_check",
            "issuer_name_1",
            "issuer_name_2",
            "issuer_name_3",
            "issuer_adl_1",
            "issuer_adl_2",
            "issuer_adl_3",
            "issuer_adl_4",
            "issuer_sort_key",
            "issuer_type",
            "issuer_status",
            "issuer_del_date",
            "issuer_transaction",
            "issuer_state_code",
            "issuer_update_date",
        ],
    },
    "issue": {
        "table": "issue",
        "staging_table": "stg_issue",
        "pk_columns": ["issuer_num", "issue_num"],
        "columns": [
            "issuer_num",
            "issue_num",
            "issue_check",
            "issue_desc_1",
            "issue_desc_2",
            "issue_adl_1",
            "issue_adl_2",
            "issue_adl_3",
            "issue_adl_4",
            "issue_status",
            "dated_date",
            "maturity_date",
            "partial_maturity",
            "rate",
            "govt_stimulus_program",
            "issue_transaction",
            "issue_update_date",
        ],
    },
    "issue_attr": {
        "table": "issue_attribute",
        "staging_table": "stg_issue_attribute",
        "pk_columns": ["issuer_num", "issue_num"],
        "columns": [
            "issuer_num",
            "issue_num",
            "alternative_min_tax",
            "bank_q",
            "callable",
            "activity_date",
            "first_coupon_date",
            "init_pub_off",
            "payment_frequency",
            "currency_code",
            "domicile_code",
            "underwriter",
            "us_cfi_code",
            "closing_date",
            "ticker_symbol",
            "iso_cfi",
            "depos_eligible",
            "pre_refund",
            "refundable",
            "remarketed",
            "sinking_fund",
            "taxable",
            "form",
            "enhancements",
            "fund_distrb_policy",
            "fund_inv_policy",
            "fund_type",
            "guarantee",
            "income_type",
            "insured_by",
            "ownership_restr",
            "payment_status",
            "preferred_type",
            "putable",
            "rate_type",
            "redemption",
            "source_doc",
            "sponsoring",
            "voting_rights",
            "warrant_assets",
            "warrant_status",
            "warrant_type",
            "where_traded",
            "auditor",
            "paying_agent",
            "tender_agent",
            "xfer_agent",
            "bond_counsel",
            "financial_advisor",
            "municipal_sale_date",
            "sale_type",
            "offering_amount",
            "offering_amount_code",
        ],
    },
}


# =============================================================================
# FILE READING & CLEANING
# =============================================================================


def is_footer(line: str) -> bool:
    """Check if line is the trailer record (starts with 999999)."""
    return line.startswith("999999|") or line.startswith("999999")


def clean_line(line: str) -> str:
    """Strip newlines, carriage returns, and EOF marker (ASCII 26 / 0x1A)."""
    return line.rstrip("\n\r\x1a")


def read_and_clean_file(filepath: Path) -> list[str]:
    """Read file, clean lines, and exclude footer row."""
    lines: list[str] = []
    with open(filepath, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = clean_line(raw_line)
            if not line:
                continue
            if is_footer(line):
                print(f"  Skipping footer: {line[:50]}...")
                continue
            lines.append(line)
    return lines


def lines_to_copy_buffer(lines: list[str]) -> StringIO:
    """Convert cleaned lines to a StringIO buffer for COPY."""
    buffer = StringIO()
    for line in lines:
        buffer.write(line + "\n")
    buffer.seek(0)
    return buffer


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================


def truncate_staging(cur: psycopg2.extensions.cursor, config: FileConfig) -> None:
    """Truncate the staging table."""
    cur.execute(
        sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(config["staging_table"]))
    )


def copy_to_staging(
    cur: psycopg2.extensions.cursor, config: FileConfig, buffer: TextIO
) -> None:
    """COPY data from buffer into staging table."""
    columns = sql.SQL(", ").join(sql.Identifier(c) for c in config["columns"])
    copy_sql = sql.SQL(
        "COPY {} ({}) FROM STDIN WITH (FORMAT csv, DELIMITER '|', NULL '')"
    ).format(sql.Identifier(config["staging_table"]), columns)
    cur.copy_expert(copy_sql, buffer)


def upsert_to_master(cur: psycopg2.extensions.cursor, config: FileConfig) -> int:
    """
    Upsert from staging to master table using INSERT ... ON CONFLICT.

    Returns number of rows affected.
    """
    columns = config["columns"]
    pk_cols = config["pk_columns"]
    non_pk_cols = [c for c in columns if c not in pk_cols]

    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
    pk_list = sql.SQL(", ").join(sql.Identifier(c) for c in pk_cols)

    set_clause = sql.SQL(", ").join(
        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
        for c in non_pk_cols
    )

    upsert_sql = sql.SQL(
        """
        INSERT INTO {master} ({columns})
        SELECT {columns} FROM {staging}
        ON CONFLICT ({pk}) DO UPDATE SET {set_clause}
    """
    ).format(
        master=sql.Identifier(config["table"]),
        staging=sql.Identifier(config["staging_table"]),
        columns=col_list,
        pk=pk_list,
        set_clause=set_clause,
    )

    cur.execute(upsert_sql)
    return cur.rowcount


# =============================================================================
# MAIN LOADER
# =============================================================================


def load_file(filepath: Path, file_type: str, db_config: DbConfig) -> LoadResult:
    """Load a single CUSIP file into the database."""
    if file_type not in FILE_CONFIG:
        raise ValueError(f"Unknown file type: {file_type}")

    config = FILE_CONFIG[file_type]
    print(f"\n{'=' * 60}")
    print(f"Loading {file_type}: {filepath}")
    print(f"  Target table: {config['table']}")
    print(f"{'=' * 60}")

    print("  Reading file...")
    lines = read_and_clean_file(filepath)
    print(f"  Found {len(lines)} data rows (excluding footer)")

    if not lines:
        print("  No data rows to load. Skipping.")
        return {
            "file": str(filepath),
            "type": file_type,
            "rows_read": 0,
            "rows_upserted": 0,
            "status": "skipped",
        }

    buffer = lines_to_copy_buffer(lines)

    conn = psycopg2.connect(**db_config)
    try:
        with conn, conn.cursor() as cur:
            print("  Truncating staging table...")
            truncate_staging(cur, config)

            print("  COPYing to staging table...")
            copy_to_staging(cur, config, buffer)

            print("  Upserting to master table...")
            rows_affected = upsert_to_master(cur, config)
            print(f"  Upserted {rows_affected} rows")

        print("  COMMIT successful")
        return {
            "file": str(filepath),
            "type": file_type,
            "rows_read": len(lines),
            "rows_upserted": rows_affected,
            "status": "success",
        }

    except Exception as e:
        conn.rollback()
        print(f"  ERROR: {e}")
        print("  ROLLBACK performed")
        return {
            "file": str(filepath),
            "type": file_type,
            "rows_read": len(lines),
            "rows_upserted": 0,
            "status": "error",
            "error": str(e),
        }
    finally:
        conn.close()


def detect_file_type(filename: str) -> str | None:
    """Auto-detect file type from CUSIP naming convention."""
    name = filename.upper()
    if name.endswith("R.PIP"):
        return "issuer"
    elif name.endswith("E.PIP"):
        return "issue"
    elif name.endswith("A.PIP"):
        return "issue_attr"
    return None
