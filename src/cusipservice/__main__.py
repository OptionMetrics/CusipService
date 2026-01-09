"""CLI entry point for CUSIP File Loader."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cusipservice.loader import DbConfig, LoadResult, detect_file_type, load_file


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Load CUSIP PIF files into PostgreSQL")
    parser.add_argument("files", nargs="+", help="Path(s) to PIF file(s)")
    parser.add_argument(
        "--type",
        choices=["issuer", "issue", "issue_attr"],
        help="File type (auto-detected from suffix if not specified)",
    )
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", default=5432, type=int, help="Database port")
    parser.add_argument("--dbname", required=True, help="Database name")
    parser.add_argument("--user", required=True, help="Database user")
    parser.add_argument("--password", default="", help="Database password")

    args = parser.parse_args()

    db_config: DbConfig = {
        "host": args.host,
        "port": args.port,
        "dbname": args.dbname,
        "user": args.user,
        "password": args.password,
    }

    results: list[LoadResult] = []
    has_error = False

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"ERROR: File not found: {filepath}")
            sys.exit(1)

        file_type = args.type or detect_file_type(path.name)
        if not file_type:
            print(f"ERROR: Cannot detect file type for {filepath}. Use --type.")
            sys.exit(1)

        result = load_file(path, file_type, db_config)
        results.append(result)

        if result.get("status") == "error":
            has_error = True

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for r in results:
        status = r.get("status", "unknown")
        if status == "success":
            status_icon = "+"
        elif status == "error":
            status_icon = "x"
        else:
            status_icon = "-"
        file_type = r.get("type", "unknown")
        rows_read = r.get("rows_read", 0)
        rows_upserted = r.get("rows_upserted", 0)
        print(
            f"  {status_icon} {file_type:12} | {rows_read:>8} read "
            f"| {rows_upserted:>8} upserted | {status}"
        )

    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
