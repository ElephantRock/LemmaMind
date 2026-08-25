#!/usr/bin/env python3
"""Run live deterministic-evidence coverage against pinned pilot sources."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lemmamind.pilot_coverage import dump_report_json, report_markdown
from lemmamind.pilot_coverage_v2 import run_live_coverage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        default="eval/pilot/coverage/external-v1.yaml",
        help="Coverage specification YAML",
    )
    parser.add_argument("--json", dest="json_output", help="Write JSON report to this path")
    parser.add_argument("--markdown", dest="markdown_output", help="Write Markdown report to this path")
    parser.add_argument(
        "--workspace",
        help="Persistent workspace for SQLite/object storage; temporary by default",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_live_coverage(
        args.spec,
        token=os.environ.get("GITHUB_TOKEN"),
        workspace=args.workspace,
    )
    json_text = dump_report_json(report)
    markdown_text = report_markdown(report)

    if args.json_output:
        path = Path(args.json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")

    if args.markdown_output:
        path = Path(args.markdown_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
