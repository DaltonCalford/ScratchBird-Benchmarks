#!/usr/bin/env python3
"""Benchmark run provenance helpers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


PROVENANCE_SCHEMA_VERSION = 1
PROVENANCE_FILENAME = "run-provenance.json"

_CMAKE_CACHE_KEYS = (
    "CMAKE_BUILD_TYPE",
    "CMAKE_C_COMPILER",
    "CMAKE_CXX_COMPILER",
    "CMAKE_GENERATOR",
    "CMAKE_SYSTEM_NAME",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_shell_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def git_repo_identity(repo_root: Path) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    payload: Dict[str, Any] = {
        "path": str(repo_root),
        "git_head": None,
        "git_dirty": None,
        "git_branch": None,
    }

    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload["git_head"] = head.stdout.strip()
    except Exception:
        return payload

    try:
        branch = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload["git_branch"] = branch.stdout.strip()
    except Exception:
        payload["git_branch"] = None

    try:
        dirty = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload["git_dirty"] = bool(dirty.stdout.strip())
    except Exception:
        payload["git_dirty"] = None

    return payload


def _find_cmake_build_dir(binary_path: Path, repo_root: Path) -> Optional[Path]:
    repo_root = repo_root.resolve()
    current = binary_path.resolve().parent
    while True:
        cache_path = current / "CMakeCache.txt"
        if cache_path.exists():
            return current
        if current == repo_root or current.parent == current:
            return None
        current = current.parent


def _parse_cmake_cache(cache_path: Path) -> Dict[str, str]:
    selected: Dict[str, str] = {}
    if not cache_path.exists():
        return selected
    for raw_line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line or raw_line.startswith(("//", "#")) or "=" not in raw_line or ":" not in raw_line:
            continue
        name_type, value = raw_line.split("=", 1)
        name, _cache_type = name_type.split(":", 1)
        if name in _CMAKE_CACHE_KEYS:
            selected[name] = value
    return selected


def _selected_environment() -> Dict[str, str]:
    prefixes = ("BENCHMARK_", "SCRATCHBIRD_", "STRESS_", "TPC_")
    selected = {
        key: value
        for key, value in os.environ.items()
        if key.startswith(prefixes)
    }
    return dict(sorted(selected.items()))


def _string_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(Path(value).expanduser().resolve())


def _capture_scratchbird_runtime(project_dir: Path) -> Dict[str, Any]:
    port_env_path = project_dir / ".benchmark-engine-ports" / "scratchbird.env"
    port_env = parse_shell_env_file(port_env_path)

    runtime_env_path = Path(port_env["BENCHMARK_SCRATCHBIRD_RUNTIME_ENV"]).resolve()
    runtime_env = parse_shell_env_file(runtime_env_path)

    root_path = Path(port_env["BENCHMARK_SCRATCHBIRD_ROOT"]).resolve()
    connections_json_path = root_path / "profiles" / "connections.json"

    server_binary_path = Path(runtime_env["SCRATCHBIRD_SB_SERVER"]).resolve()
    server_binary_stat = server_binary_path.stat()

    scratchbird_root = server_binary_path
    while scratchbird_root.name:
        candidate = scratchbird_root / ".git"
        if candidate.exists():
            break
        if scratchbird_root.parent == scratchbird_root:
            break
        scratchbird_root = scratchbird_root.parent
    if not (scratchbird_root / ".git").exists():
        scratchbird_root = (project_dir.parent / "ScratchBird").resolve()

    build_dir = _find_cmake_build_dir(server_binary_path, scratchbird_root)
    cache_path = build_dir / "CMakeCache.txt" if build_dir else None

    runtime = {
        "root": str(root_path),
        "port_env_file": str(port_env_path.resolve()),
        "port_env_sha256": sha256_file(port_env_path),
        "port_env": port_env,
        "runtime_env_file": str(runtime_env_path),
        "runtime_env_sha256": sha256_file(runtime_env_path),
        "runtime_env": runtime_env,
        "connections_json_file": str(connections_json_path),
        "connections_json_sha256": sha256_file(connections_json_path) if connections_json_path.exists() else None,
        "server_binary": {
            "path": str(server_binary_path),
            "realpath": str(server_binary_path.resolve()),
            "size_bytes": server_binary_stat.st_size,
            "mtime_ns": server_binary_stat.st_mtime_ns,
            "sha256": sha256_file(server_binary_path),
        },
        "build_identity": {
            "scratchbird_repo": git_repo_identity(scratchbird_root),
            "build_dir": str(build_dir.resolve()) if build_dir else None,
            "cmake_cache_file": str(cache_path.resolve()) if cache_path and cache_path.exists() else None,
            "cmake_cache_sha256": sha256_file(cache_path) if cache_path and cache_path.exists() else None,
            "cmake_cache_selected": _parse_cmake_cache(cache_path) if cache_path else {},
        },
    }

    pinned = (
        bool(runtime["server_binary"]["path"])
        and bool(runtime["server_binary"]["realpath"])
        and bool(runtime["server_binary"]["sha256"])
        and bool(runtime["build_identity"]["scratchbird_repo"]["git_head"])
    )

    runtime["pinning"] = {
        "status": "pinned" if pinned else "unpinned",
        "comparison_eligible": pinned,
        "reason": (
            "absolute ScratchBird binary path, file fingerprint, and repo/build identity recorded"
            if pinned
            else "required ScratchBird binary provenance fields are missing"
        ),
    }
    return runtime


def capture_run_provenance(
    *,
    project_dir: Path,
    engine: str,
    suite: str,
    output_dir: Path,
    runner_script: Path,
    runner_cwd: Path,
    runner_argv: Iterable[str],
    python_executable: Optional[str],
    runtime_options: Dict[str, Any],
) -> Dict[str, Any]:
    project_dir = project_dir.resolve()
    output_dir = output_dir.resolve()
    runner_script = runner_script.resolve()
    runner_cwd = runner_cwd.resolve()

    payload: Dict[str, Any] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "capture_kind": "benchmark_run_provenance",
        "captured_at_utc": utc_now_iso(),
        "engine": engine,
        "suite": suite,
        "artifact_root": str(output_dir),
        "runner": {
            "script_path": str(runner_script),
            "cwd": str(runner_cwd),
            "argv": list(runner_argv),
            "python_executable": python_executable,
        },
        "runtime_options": runtime_options,
        "benchmark_repo": git_repo_identity(project_dir),
        "selected_environment": _selected_environment(),
    }

    if engine == "scratchbird":
        payload["scratchbird_runtime"] = _capture_scratchbird_runtime(project_dir)

    return payload


def write_run_provenance(output_path: Path, payload: Dict[str, Any]) -> None:
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def provenance_file_for_result(result_file: Path) -> Path:
    return result_file.parent / PROVENANCE_FILENAME


def validate_scratchbird_result_provenance(result_file: Path) -> Dict[str, Any]:
    result_payload = load_json(result_file)
    engine = result_payload.get("metadata", {}).get("engine")
    if engine != "scratchbird":
        return {}

    provenance_path = provenance_file_for_result(result_file)
    if not provenance_path.exists():
        raise ValueError(f"ScratchBird result is missing {PROVENANCE_FILENAME}: {result_file}")

    provenance = load_json(provenance_path)
    scratchbird_runtime = provenance.get("scratchbird_runtime") or {}
    pinning = scratchbird_runtime.get("pinning") or {}
    server_binary = scratchbird_runtime.get("server_binary") or {}
    runner = provenance.get("runner") or {}

    required = {
        "schema_version": provenance.get("schema_version") == PROVENANCE_SCHEMA_VERSION,
        "capture_kind": provenance.get("capture_kind") == "benchmark_run_provenance",
        "engine": provenance.get("engine") == "scratchbird",
        "runner_script": os.path.isabs(str(runner.get("script_path", ""))),
        "runner_argv": isinstance(runner.get("argv"), list) and len(runner["argv"]) > 0,
        "pinning_status": pinning.get("status") == "pinned",
        "comparison_eligible": pinning.get("comparison_eligible") is True,
        "binary_path": os.path.isabs(str(server_binary.get("path", ""))),
        "binary_realpath": os.path.isabs(str(server_binary.get("realpath", ""))),
        "binary_sha256": isinstance(server_binary.get("sha256"), str) and len(server_binary["sha256"]) == 64,
        "git_head": bool(((scratchbird_runtime.get("build_identity") or {}).get("scratchbird_repo") or {}).get("git_head")),
    }

    failed = [name for name, ok in required.items() if not ok]
    if failed:
        raise ValueError(
            f"ScratchBird result is unpinned and cannot be compared: {result_file} "
            f"(missing {', '.join(failed)})"
        )

    return provenance
