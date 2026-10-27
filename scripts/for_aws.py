"""Generate an AWS S3 version of the Zetaris registration SQL.

    python scripts/for_aws.py --bucket overturn-733285734878 --region ap-southeast-2

Writes out/register_zetaris_aws.sql. The MinIO defaults in the shipped script
(localhost:9000, path-style access) are replaced with the regional AWS S3
endpoint and virtual-hosted access. Everything else is unchanged.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "register_zetaris_sources.sql"
TARGET = ROOT / "out" / "register_zetaris_aws.sql"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True, help="S3 bucket holding data/sources/*.csv")
    parser.add_argument("--region", default="ap-southeast-2", help="AWS region of the bucket")
    parser.add_argument("--out", default=str(TARGET))
    args = parser.parse_args()

    text = SOURCE.read_text(encoding="utf-8")

    def rewrite(match: re.Match[str]) -> str:
        block = match.group(0)
        block = block.replace("s3a://overturn/", f"s3a://{args.bucket}/")
        block = block.replace('useS3PathStyleAccess "true"', 'useS3PathStyleAccess "false"')
        block = block.replace(
            's3Endpoint "http://localhost:9000"',
            f's3Endpoint "s3.{args.region}.amazonaws.com"',
        )
        return block

    pattern = re.compile(
        r"CREATE LIGHTNING FILESTORE TABLE .*?OPTIONS \(.*?\);",
        re.DOTALL,
    )
    output, count = pattern.subn(rewrite, text)
    if count != 7:
        raise SystemExit(f"expected 7 filestore tables, rewrote {count}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"wrote {out_path}  ({count} tables, bucket {args.bucket}, region {args.region})")


if __name__ == "__main__":
    main()
