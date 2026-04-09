#!/usr/bin/env python3
"""Capture benchmark runner provenance for one artifact root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmark_provenance import capture_run_provenance, write_run_provenance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture benchmark run provenance")
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runner-script", type=Path, required=True)
    parser.add_argument("--runner-cwd", type=Path, required=True)
    parser.add_argument("--python-executable", default=None)
    parser.add_argument("--output-file", type=Path, default=None)
    parser.add_argument("--runner-argv", action="append", default=[])
    parser.add_argument("--runtime-option", action="append", default=[])
    return parser.parse_args()


def parse_runtime_options(raw_options: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in raw_options:
        if "=" not in raw:
            raise SystemExit(f"invalid --runtime-option {raw!r}; expected KEY=VALUE")
        key, value = raw.split("=", 1)
        parsed[key] = value
    return parsed


def main() -> int:
    args = parse_args()
    output_file = args.output_file or (args.output_dir / "run-provenance.json")

    payload = capture_run_provenance(
        project_dir=args.project_dir,
        engine=args.engine,
        suite=args.suite,
        output_dir=args.output_dir,
        runner_script=args.runner_script,
        runner_cwd=args.runner_cwd,
        runner_argv=args.runner_argv,
        python_executable=args.python_executable,
        runtime_options=parse_runtime_options(args.runtime_option),
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_run_provenance(output_file, payload)
    print(output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
