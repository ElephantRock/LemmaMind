from __future__ import annotations

import argparse
import json

from lemmamind.observation_readiness import evaluate_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate hard golden Observation readiness")
    parser.add_argument(
        "--spec",
        default="eval/pilot/observation-readiness-v1.yaml",
        help="Path to the versioned readiness specification",
    )
    parser.add_argument("--json", dest="json_path", help="Optional JSON output path")
    args = parser.parse_args()

    report = evaluate_readiness(args.spec)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            handle.write(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
