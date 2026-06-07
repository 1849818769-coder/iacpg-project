#!/usr/bin/env python3
"""Shared helpers for loading and validating MiBench meta files."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_WARNED_META_FILES: set[str] = set()


def load_meta_checked(meta_path: Path, expected_case_id: str, expected_arch: str) -> dict | None:
    """Load a meta YAML file and warn if its internal identifiers disagree.

    The evaluation scripts use the filename / loop identifiers as the source of
    truth for locating analysis directories. If the YAML body contains stale
    fields such as `case_id: easy_001`, we keep evaluating against the real
    `simple_001` directory but print a warning once so the inconsistency is
    visible.
    """
    if not meta_path.exists():
        return None

    with open(meta_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    mismatches = []
    meta_case_id = meta.get("case_id")
    meta_arch = meta.get("platform")

    if meta_case_id and meta_case_id != expected_case_id:
        mismatches.append(f"case_id={meta_case_id!r} != {expected_case_id!r}")
    if meta_arch and meta_arch != expected_arch:
        mismatches.append(f"platform={meta_arch!r} != {expected_arch!r}")

    if mismatches:
        meta_key = str(meta_path)
        if meta_key not in _WARNED_META_FILES:
            details = "; ".join(mismatches)
            print(
                f"WARNING: meta mismatch in {meta_path}: {details}. "
                f"Evaluation will continue using the filename/directory identifiers "
                f"({expected_case_id}, {expected_arch}).",
                file=sys.stderr,
            )
            _WARNED_META_FILES.add(meta_key)

    return meta
