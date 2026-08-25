#!/usr/bin/env python3
"""Run the first golden-driven Evidence -> Observation probe."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lemmamind.pilot_observations import run_openbot_observation_probe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage-spec",
        default="eval/pilot/coverage/external-v1.yaml",
    )
    parser.add_argument(
        "--golden-case",
        default="eval/pilot/cases/external-openbot-capability-authority.yaml",
    )
    parser.add_argument("--workspace")
    parser.add_argument("--json", dest="json_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_openbot_observation_probe(
        coverage_spec_path=args.coverage_spec,
        golden_case_path=args.golden_case,
        token=os.environ.get("GITHUB_TOKEN"),
        workspace=args.workspace,
    )
    text = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.json_output:
        path = Path(args.json_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
