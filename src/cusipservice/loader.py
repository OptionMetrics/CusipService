"""
CUSIP File Loader

Loads CUSIP PIF files (Issuer, Issue, Issue Attributes) into PostgreSQL
with staging table + upsert pattern in a single transaction.

Supports loading from:
- Local filesystem (Path objects)
- S3 buckets (via FileInfo from file_source module)
- Pre-read lines (for testing or custom sources)
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, TypedDict

import psycopg2
from psycopg2 import sql

if TYPE_CHECKING:
    from cusipservice.file_source import FileInfo, LocalFileSource, S3FileSource

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


def clean_lines(raw_lines: list[str]) -> list[str]:
    """
    Clean a list of raw lines, removing empty lines and footer.

    Args:
        raw_lines: List of raw lines (may include newlines, footers, etc.)

    Returns:
        List of cleaned data lines
    """
    lines: list[str] = []
    for raw_line in raw_lines:
        line = clean_line(raw_line)
        if not line:
            continue
        if is_footer(line):
            print(f"  Skipping footer: {line[:50]}...")
            continue
        lines.append(line)
    return lines


def read_and_clean_file(filepath: Path) -> list[str]:
    """Read file from local filesystem, clean lines, and exclude footer row."""
    with open(filepath, encoding="utf-8", errors="replace") as f:
        raw_lines = f.read().splitlines()
    return clean_lines(raw_lines)


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


def load_from_lines(
    lines: list[str],
    file_type: str,
    db_config: DbConfig,
    display_name: str = "<memory>",
) -> LoadResult:
    """
    Load CUSIP data from pre-read lines into the database.

    This function is useful for:
    - Loading from S3 (read lines first, then load)
    - Testing with synthetic data
    - Custom file sources

    Args:
        lines: Raw lines from the file (will be cleaned)
        file_type: Type of file ('issuer', 'issue', 'issue_attr')
        db_config: Database connection configuration
        display_name: Name to display in logs and results

    Returns:
        LoadResult with status and row counts
    """
    if file_type not in FILE_CONFIG:
        raise ValueError(f"Unknown file type: {file_type}")

    config = FILE_CONFIG[file_type]
    print(f"\n{'=' * 60}")
    print(f"Loading {file_type}: {display_name}")
    print(f"  Target table: {config['table']}")
    print(f"{'=' * 60}")

    print("  Cleaning lines...")
    cleaned_lines = clean_lines(lines)
    print(f"  Found {len(cleaned_lines)} data rows (excluding footer)")

    if not cleaned_lines:
        print("  No data rows to load. Skipping.")
        return {
            "file": display_name,
            "type": file_type,
            "rows_read": 0,
            "rows_upserted": 0,
            "status": "skipped",
        }

    buffer = lines_to_copy_buffer(cleaned_lines)

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
            "file": display_name,
            "type": file_type,
            "rows_read": len(cleaned_lines),
            "rows_upserted": rows_affected,
            "status": "success",
        }

    except Exception as e:
        conn.rollback()
        print(f"  ERROR: {e}")
        print("  ROLLBACK performed")
        return {
            "file": display_name,
            "type": file_type,
            "rows_read": len(cleaned_lines),
            "rows_upserted": 0,
            "status": "error",
            "error": str(e),
        }
    finally:
        conn.close()


def load_from_source(
    file_info: FileInfo,
    file_type: str,
    db_config: DbConfig,
    file_source: LocalFileSource | S3FileSource,
) -> LoadResult:
    """
    Load a CUSIP file using the file source abstraction.

    This is the preferred method for loading files as it supports
    both local filesystem and S3 sources transparently.

    Args:
        file_info: FileInfo object describing the file location
        file_type: Type of file ('issuer', 'issue', 'issue_attr')
        db_config: Database connection configuration
        file_source: File source instance for reading the file

    Returns:
        LoadResult with status and row counts
    """
    print(f"  Reading from {file_info.source}: {file_info.display_path}")
    raw_lines = file_source.read_file(file_info)

    return load_from_lines(
        lines=raw_lines,
        file_type=file_type,
        db_config=db_config,
        display_name=file_info.display_path,
    )
