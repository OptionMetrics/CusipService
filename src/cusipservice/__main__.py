"""CLI entry point for CUSIP File Loader."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from cusipservice.file_source import (
    FileInfo,
    S3FileSource,
)
from cusipservice.loader import (
    DbConfig,
    LoadResult,
    detect_file_type,
    load_file,
    load_from_source,
)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load CUSIP PIP files into PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load local files
  %(prog)s /data/CED01-15R.PIP --dbname cusip --user cusip_app

  # Load from S3 by date (uses AWS_PROFILE if set)
  %(prog)s --s3-bucket cusip-pip-files --date 2024-01-15 --dbname cusip --user cusip_app

  # Load specific S3 file
  %(prog)s --s3-bucket cusip-pip-files --s3-key pip/CED01-15R.PIP --type issuer --dbname cusip --user cusip_app

  # Use AWS SSO profile
  AWS_PROFILE=my-profile %(prog)s --s3-bucket cusip-pip-files --date 2024-01-15 --dbname cusip --user cusip_app
        """,
    )

    # File source options (mutually exclusive groups)
    source_group = parser.add_argument_group("file source")
    source_group.add_argument(
        "files",
        nargs="*",
        help="Path(s) to local PIP file(s)",
    )
    source_group.add_argument(
        "--s3-bucket",
        help="S3 bucket name for PIP files",
    )
    source_group.add_argument(
        "--s3-prefix",
        default="pip/",
        help="S3 prefix/path for PIP files (default: pip/)",
    )
    source_group.add_argument(
        "--s3-key",
        help="Specific S3 key to load (use with --s3-bucket)",
    )
    source_group.add_argument(
        "--s3-region",
        help="AWS region for S3 bucket (optional, uses default if not set)",
    )
    source_group.add_argument(
        "--date",
        help="Date to load files for (YYYY-MM-DD format, used with --s3-bucket)",
    )

    # File type option
    parser.add_argument(
        "--type",
        choices=["issuer", "issue", "issue_attr"],
        help="File type (auto-detected from suffix if not specified)",
    )

    # Database options
    db_group = parser.add_argument_group("database")
    db_group.add_argument("--host", default="localhost", help="Database host")
    db_group.add_argument("--port", default=5432, type=int, help="Database port")
    db_group.add_argument("--dbname", required=True, help="Database name")
    db_group.add_argument("--user", required=True, help="Database user")
    db_group.add_argument("--password", default="", help="Database password")

    args = parser.parse_args()

    # Validate arguments
    if args.s3_bucket and args.files:
        parser.error("Cannot specify both local files and --s3-bucket")

    if not args.s3_bucket and not args.files:
        parser.error("Must specify either local files or --s3-bucket")

    if args.s3_key and not args.s3_bucket:
        parser.error("--s3-key requires --s3-bucket")

    if args.date and not args.s3_bucket:
        parser.error("--date requires --s3-bucket")

    if args.s3_bucket and not args.s3_key and not args.date:
        parser.error("--s3-bucket requires either --s3-key or --date")

    db_config: DbConfig = {
        "host": args.host,
        "port": args.port,
        "dbname": args.dbname,
        "user": args.user,
        "password": args.password,
    }

    results: list[LoadResult] = []
    has_error = False

    if args.files:
        # Load from local files
        results, has_error = _load_local_files(args.files, args.type, db_config)
    elif args.s3_key:
        # Load specific S3 file
        results, has_error = _load_s3_file(
            bucket=args.s3_bucket,
            key=args.s3_key,
            file_type=args.type,
            region=args.s3_region,
            db_config=db_config,
        )
    else:
        # Load from S3 by date
        results, has_error = _load_s3_by_date(
            bucket=args.s3_bucket,
            prefix=args.s3_prefix,
            date_str=args.date,
            region=args.s3_region,
            db_config=db_config,
        )

    _print_summary(results)
    sys.exit(1 if has_error else 0)


def _load_local_files(
    filepaths: list[str],
    file_type: str | None,
    db_config: DbConfig,
) -> tuple[list[LoadResult], bool]:
    """Load files from local filesystem."""
    results: list[LoadResult] = []
    has_error = False

    for filepath in filepaths:
        path = Path(filepath)
        if not path.exists():
            print(f"ERROR: File not found: {filepath}")
            sys.exit(1)

        detected_type = file_type or detect_file_type(path.name)
        if not detected_type:
            print(f"ERROR: Cannot detect file type for {filepath}. Use --type.")
            sys.exit(1)

        result = load_file(path, detected_type, db_config)
        results.append(result)

        if result.get("status") == "error":
            has_error = True

    return results, has_error


def _load_s3_file(
    bucket: str,
    key: str,
    file_type: str | None,
    region: str | None,
    db_config: DbConfig,
) -> tuple[list[LoadResult], bool]:
    """Load a specific file from S3."""
    filename = key.split("/")[-1]
    detected_type = file_type or detect_file_type(filename)
    if not detected_type:
        print(f"ERROR: Cannot detect file type for {key}. Use --type.")
        sys.exit(1)

    file_source = S3FileSource(bucket=bucket, region=region)
    file_info = FileInfo(
        name=filename,
        source="s3",
        s3_bucket=bucket,
        s3_key=key,
    )

    result = load_from_source(file_info, detected_type, db_config, file_source)
    has_error = result.get("status") == "error"

    return [result], has_error


def _load_s3_by_date(
    bucket: str,
    prefix: str,
    date_str: str,
    region: str | None,
    db_config: DbConfig,
) -> tuple[list[LoadResult], bool]:
    """Load all files for a date from S3."""
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        print(f"ERROR: Invalid date format: {date_str}. Expected YYYY-MM-DD")
        sys.exit(1)

    file_source = S3FileSource(bucket=bucket, prefix=prefix, region=region)
    files = file_source.find_files_for_date(target_date)

    results: list[LoadResult] = []
    has_error = False
    load_order = ["issuer", "issue", "issue_attr"]

    file_map = {
        "issuer": files.issuer,
        "issue": files.issue,
        "issue_attr": files.issue_attr,
    }

    for file_type in load_order:
        file_info = file_map.get(file_type)
        if file_info is None:
            print(f"  No {file_type} file found for {target_date}")
            results.append(
                {
                    "file": "",
                    "type": file_type,
                    "rows_read": 0,
                    "rows_upserted": 0,
                    "status": "skipped",
                }
            )
            continue

        result = load_from_source(file_info, file_type, db_config, file_source)
        results.append(result)

        if result.get("status") == "error":
            has_error = True
            # Stop on error to prevent FK violations
            break

    return results, has_error


def _print_summary(results: list[LoadResult]) -> None:
    """Print load results summary."""
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


if __name__ == "__main__":
    main()
