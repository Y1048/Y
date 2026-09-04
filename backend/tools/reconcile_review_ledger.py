"""Rebuild the bounded source-review ledger from the current checkout.

This tool is repository-local and offline: it imports no project runtime module,
opens no socket, creates no SDK/DDS entity, and writes only review artifacts.
Existing semantic-review decisions are preserved; continuation delta CSV files
may explicitly promote paths to ``full_text_review``. New unreviewed files default
to ``static_only``.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
from pathlib import Path

from build_code_index import CollectFiles, ROOT


LEDGER = ROOT / "logs" / "review" / "20260903" / "source_checks.csv"
SUMMARY = ROOT / "logs" / "review" / "20260903" / "source_checks_summary_20260904.json"
VALID_SEMANTIC = {"full_text_review", "static_only"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _semantic_map() -> tuple[dict[str, str], set[str]]:
    result: dict[str, str] = {}
    promoted: set[str] = set()
    for row in _read_csv(LEDGER):
        value = row.get("semantic_review", "").strip()
        path = row.get("path", "").strip()
        if path and value in VALID_SEMANTIC:
            result[path] = value

    review_dir = LEDGER.parent
    for delta in sorted(review_dir.glob("source_checks_delta_*.csv")):
        for row in _read_csv(delta):
            path = row.get("path", "").strip()
            value = row.get("semantic_review", "").strip()
            if path and value in VALID_SEMANTIC:
                result[path] = value
                if value == "full_text_review":
                    promoted.add(path)
    return result, promoted


def _static_check(path: Path, raw: bytes) -> tuple[str, str]:
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return "text_decode_fail", f"UnicodeDecodeError:{exc}"

    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            ast.parse(source)
        except SyntaxError as exc:
            return "python_ast_fail", f"SyntaxError:{exc.msg}@{exc.lineno}"
        return "python_ast_pass", ""
    if suffix == ".json":
        try:
            json.loads(source)
        except json.JSONDecodeError as exc:
            return "json_parse_fail", f"JSONDecodeError:{exc.msg}@{exc.lineno}"
        return "json_parse_pass", ""
    return "text_read_only", ""


def build_rows() -> tuple[list[dict[str, str]], dict[str, object]]:
    semantics, promoted = _semantic_map()
    rows: list[dict[str, str]] = []
    current_paths: set[str] = set()

    for path in CollectFiles(ROOT):
        relative = path.relative_to(ROOT).as_posix()
        current_paths.add(relative)
        raw = path.read_bytes()
        static_check, error = _static_check(path, raw)
        try:
            lines = len(raw.decode("utf-8-sig").splitlines())
        except UnicodeDecodeError:
            lines = 0
        rows.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "lines": str(lines),
                "static_check": static_check,
                "error": error,
                "semantic_review": semantics.get(relative, "static_only"),
            }
        )

    full = sum(row["semantic_review"] == "full_text_review" for row in rows)
    static = sum(row["semantic_review"] == "static_only" for row in rows)
    static_failures = sum(bool(row["error"]) for row in rows)
    stale_promotions = sorted(promoted - current_paths)
    summary = {
        "schema": "g1.review.source_checks.summary.v2",
        "scope_source": "backend.tools.build_code_index.CollectFiles",
        "total_current_files": len(rows),
        "full_text_review": full,
        "static_only": static,
        "static_check_failures": static_failures,
        "delta_promotions_not_in_current_scope": stale_promotions,
        "semantic_rule": (
            "Preserve prior full_text_review/static_only, overlay explicit delta "
            "records, default new files to static_only."
        ),
    }
    return rows, summary


def _csv_text(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "path",
            "sha256",
            "lines",
            "static_check",
            "error",
            "semantic_review",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rows, summary = build_rows()
    ledger_text = _csv_text(rows)
    summary_text = json.dumps(summary, indent=2) + "\n"

    if args.check:
        current_ledger = (
            LEDGER.read_text(encoding="utf-8-sig") if LEDGER.is_file() else ""
        )
        current_summary = (
            SUMMARY.read_text(encoding="utf-8") if SUMMARY.is_file() else ""
        )
        if current_ledger != ledger_text or current_summary != summary_text:
            print("[FAIL] Review ledger is stale. Run reconcile_review_ledger.py")
            print(json.dumps(summary, indent=2))
            return 1
        print("[PASS] Review ledger matches current checkout.")
        print(json.dumps(summary, indent=2))
        return 0

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(ledger_text, encoding="utf-8-sig")
    SUMMARY.write_text(summary_text, encoding="utf-8")
    print(f"Saved: {LEDGER}")
    print(f"Saved: {SUMMARY}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
