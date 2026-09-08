"""Agentic review harness for Ryan Nolan's Inventory Management feature.

Three modes: architecture, database, endpoints.
Each mode: load prompt -> collect read-only evidence -> ask Ollama for an
initial review -> run deterministic grounding checks against the real
evidence -> write a final, corrected markdown report.

This script never writes to the database, never modifies source files,
and never sends mutating (POST/PUT/PATCH/DELETE) requests to the backend.

Usage:
    python3 agentic_review.py architecture
    python3 agentic_review.py database
    python3 agentic_review.py endpoints
    python3 agentic_review.py all
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "review_prompt.json"

# Repo root: this script lives at student-Ryan_Nolan/agentic/, so root is two up.
PROJECT_ROOT = SCRIPT_DIR.resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "docs" / "evidence" / "agentic"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:0.5b"
OLLAMA_TIMEOUT_SECONDS = 90

MAX_FILE_CHARS = 4000          # per-file excerpt cap for architecture mode
MAX_SAMPLE_ROWS = 3            # sample rows per table for database mode
REDACTED = "<redacted>"

# Columns whose sample values should never be sent to the model or written
# to the report, even though the column names themselves are fine to show.
SENSITIVE_COLUMNS = {
    "contact_name", "email", "phone", "address",
}


# --------------------------------------------------------------------------
# Config / prompt loading
# --------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_prompt(filename: str) -> str:
    path = SCRIPT_DIR / filename
    if not path.exists():
        raise SystemExit(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------
# Evidence collectors
# --------------------------------------------------------------------------

def collect_architecture_evidence(config: dict[str, Any]) -> dict[str, Any]:
    files = []
    missing = []
    truncated = []

    for rel_path in config["architecture_files"]:
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            missing.append(rel_path)
            continue
        text = full_path.read_text(encoding="utf-8", errors="replace")
        is_truncated = len(text) > MAX_FILE_CHARS
        if is_truncated:
            truncated.append(rel_path)
        files.append({
            "path": rel_path,
            "characters": len(text),
            "truncated": is_truncated,
            "content": text[:MAX_FILE_CHARS],
        })

    all_text = "\n".join(f["content"] for f in files)
    assistant_text = "\n".join(
        f["content"] for f in files
        if f["path"].endswith("backend/assistant.py")
    )

    source_checks = {
        # Restock Assistant should only ever do a SELECT, never write.
        # Scoped to assistant.py specifically — products.py/suppliers.py
        # legitimately perform writes for their own CRUD routes, so
        # checking the whole bundle would always fail this check.
        "assistant_is_read_only_no_write_calls": not re.search(
            r"\b(INSERT INTO|UPDATE |DELETE FROM)\b", assistant_text, re.IGNORECASE
        ) if assistant_text else None,
        # Route-layer validation: look for an explicit empty/blank check
        # on request input before it's used (matches products/suppliers/
        # assistant's "message required" style checks).
        "route_layer_validates_request_input": bool(
            re.search(r"abort\(400", all_text)
            or re.search(r"return jsonify\(\{\"error\"", all_text)
        ),
        # Blueprint registration should live in the central app entry
        # point, not be duplicated inside individual route files.
        "blueprints_registered_in_central_app": bool(
            re.search(r"register_blueprint", all_text)
        ),
        # URL prefix consistency: every blueprint should sit under
        # /api/inventory/.
        "blueprint_prefixes_consistent": (
            all("/api/inventory" in f["content"] for f in files
                if f["path"].startswith("student-Ryan_Nolan/backend/"))
        ),
    }

    return {
        "project_root": str(PROJECT_ROOT),
        "read_only": True,
        "files": files,
        "verified_checks": {
            "configured_files": len(config["architecture_files"]),
            "present_files": len(files),
            "missing_files": missing,
            "truncated_files": truncated,
            "source_checks": source_checks,
        },
    }


def collect_database_evidence(config: dict[str, Any]) -> dict[str, Any]:
    db_path = PROJECT_ROOT / config["database"]
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    tables: dict[str, Any] = {}

    # Open strictly read-only via SQLite's URI mode, so this script cannot
    # accidentally write to the real database even if a bug were introduced.
    uri = f"file:{db_path}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        table_names = [
            row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        ]

        for table in table_names:
            create_sql_row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
                (table,),
            ).fetchone()
            create_sql = create_sql_row["sql"] if create_sql_row else ""

            columns = []
            for col in conn.execute(f"PRAGMA table_info({table})"):
                columns.append({
                    "name": col["name"],
                    "type": col["type"],
                    "not_null": bool(col["notnull"]),
                    "default": col["dflt_value"],
                    "primary_key": bool(col["pk"]),
                })

            foreign_keys = []
            for fk in conn.execute(f"PRAGMA foreign_key_list({table})"):
                foreign_keys.append({
                    "referenced_table": fk["table"],
                    "from_column": fk["from"],
                    "to_column": fk["to"],
                    "on_update": fk["on_update"],
                    "on_delete": fk["on_delete"],
                })

            indexes = []
            for idx in conn.execute(f"PRAGMA index_list({table})"):
                idx_cols = [
                    r["name"] for r in conn.execute(
                        f"PRAGMA index_info({idx['name']})"
                    )
                ]
                indexes.append({
                    "name": idx["name"],
                    "unique": bool(idx["unique"]),
                    "columns": idx_cols,
                })

            record_count = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table}"
            ).fetchone()["n"]

            sample_rows = conn.execute(
                f"SELECT * FROM {table} LIMIT {MAX_SAMPLE_ROWS}"
            ).fetchall()
            sample_records = []
            for row in sample_rows:
                record = {}
                for key in row.keys():
                    record[key] = REDACTED if key in SENSITIVE_COLUMNS else row[key]
                sample_records.append(record)

            tables[table] = {
                "record_count": record_count,
                "create_sql": create_sql,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "sample_records": sample_records,
            }

    return {
        "database": str(db_path),
        "read_only": True,
        "tables": tables,
    }


def collect_endpoints_evidence(config: dict[str, Any]) -> dict[str, Any]:
    results = []

    for endpoint in config["endpoints"]:
        name = endpoint["name"]
        url = endpoint["url"]
        health_url = endpoint.get("health_url")

        # Pre-check: verify the service is reachable before hitting the
        # real endpoint, so an unreachable backend is reported clearly
        # rather than surfacing as a raw connection-error stack trace.
        reachable = True
        reachability_note = None
        if health_url:
            try:
                health_resp = requests.get(health_url, timeout=5)
                if health_resp.status_code >= 400:
                    reachable = False
                    reachability_note = (
                        f"Health check at {health_url} returned "
                        f"{health_resp.status_code}."
                    )
            except requests.exceptions.RequestException as exc:
                reachable = False
                reachability_note = (
                    f"Health check at {health_url} failed: {exc}. "
                    f"The backend container may not be running — start it "
                    f"with `docker compose up inventory-backend` first."
                )

        if not reachable:
            results.append({
                "name": name,
                "url": url,
                "reachable": False,
                "reachability_note": reachability_note,
                "status_code": None,
                "response_json": None,
            })
            continue

        try:
            resp = requests.get(url, timeout=10)
            body = None
            try:
                body = resp.json()
            except ValueError:
                body = None
            results.append({
                "name": name,
                "url": url,
                "reachable": True,
                "reachability_note": None,
                "status_code": resp.status_code,
                "response_json": body,
            })
        except requests.exceptions.RequestException as exc:
            results.append({
                "name": name,
                "url": url,
                "reachable": False,
                "reachability_note": f"Request failed: {exc}",
                "status_code": None,
                "response_json": None,
            })

    return {
        "read_only": True,
        "method": "GET",
        "endpoints": results,
    }


# --------------------------------------------------------------------------
# Ollama review call
# --------------------------------------------------------------------------

def call_ollama(system_context: str, mode_prompt: str, evidence: dict[str, Any]) -> str:
    evidence_json = json.dumps(evidence, indent=2, default=str)
    full_prompt = (
        f"{system_context}\n\n"
        f"{mode_prompt}\n\n"
        f"Respond using exactly these section headers, in this order: "
        f"PLAN REVIEWED, OBSERVATIONS, FINDINGS, RECOMMENDATIONS, "
        f"PROPOSED ADAPTATION.\n\n"
        f"Evidence (JSON):\n{evidence_json}\n"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.RequestException as exc:
        return (
            "DECISION: ADAPT\n"
            f"The model could not be reached ({exc}). No initial review was "
            f"generated; this report relies entirely on deterministic checks."
        )


# --------------------------------------------------------------------------
# Deterministic grounding checks — one per mode, derived directly from the
# constraints stated in each mode's prompt file.
# --------------------------------------------------------------------------

def check_architecture_grounding(review_text: str, evidence: dict[str, Any]) -> list[str]:
    issues = []
    cited_paths = [f["path"] for f in evidence["files"] if f["path"] in review_text]
    if len(cited_paths) < 3:
        issues.append(
            "The architecture response cites fewer than three configured "
            "files and is too narrow for the selected review."
        )
    if re.search(r"\bmissing\b", review_text, re.IGNORECASE) and not evidence["verified_checks"]["missing_files"]:
        issues.append(
            "The response claims a file is missing, but every configured "
            "architecture file was present in the collected evidence."
        )
    return issues


def check_database_grounding(review_text: str, evidence: dict[str, Any]) -> list[str]:
    issues = []
    for table_name, table in evidence["tables"].items():
        real_count = table["record_count"]
        # Look for any other digit sequence the model attached to this
        # table name and flag it if it doesn't match the real count.
        pattern = rf"{re.escape(table_name)}[^.]{{0,40}}?(\d+)\s*(?:records|rows)"
        for match in re.finditer(pattern, review_text, re.IGNORECASE):
            claimed = int(match.group(1))
            if claimed != real_count:
                issues.append(
                    f"The {table_name} record count is {real_count}, not {claimed}."
                )
        real_columns = {c["name"] for c in table["columns"]}
        for other_table, other in evidence["tables"].items():
            if other_table == table_name:
                continue
            other_only_columns = {c["name"] for c in other["columns"]} - real_columns
            for col in other_only_columns:
                if re.search(rf"{re.escape(table_name)}[^.\n]{{0,60}}{re.escape(col)}\b", review_text):
                    issues.append(
                        f"The {table_name} discussion assigns unsupported column: {col}."
                    )
    return issues


def check_endpoints_grounding(review_text: str, evidence: dict[str, Any]) -> list[str]:
    issues = []
    if re.search(r"\b(POST|PUT|PATCH|DELETE)\b", review_text):
        issues.append(
            "The response references a mutating HTTP method (POST/PUT/"
            "PATCH/DELETE); this mode only issues GET requests."
        )
    for ep in evidence["endpoints"]:
        if not ep["reachable"] and re.search(
            rf"{re.escape(ep['name'])}[^.\n]{{0,60}}\bpass(?:ed|es)?\b",
            review_text, re.IGNORECASE,
        ):
            issues.append(
                f"{ep['name']} was unreachable but the response describes "
                f"it as passing."
            )
    return issues


GROUNDING_CHECKS = {
    "architecture": check_architecture_grounding,
    "database": check_database_grounding,
    "endpoints": check_endpoints_grounding,
}


# --------------------------------------------------------------------------
# Final report assembly
# --------------------------------------------------------------------------

def build_final_review(mode: str, evidence: dict[str, Any], grounding_issues: list[str]) -> str:
    lines = ["OBSERVATIONS"]

    if mode == "architecture":
        vc = evidence["verified_checks"]
        lines.append(f"- {vc['present_files']} of {vc['configured_files']} configured architecture files were present.")
        if vc["missing_files"]:
            lines.append(f"- Missing files: {', '.join(vc['missing_files'])}.")
        lines.append("- The collector opened configured files read-only and retained bounded excerpts.")
        for check, result in vc["source_checks"].items():
            lines.append(f"- Configured source check `{check}`: {result}.")

    elif mode == "database":
        for table, data in evidence["tables"].items():
            col_names = ", ".join(c["name"] for c in data["columns"])
            lines.append(f"- `{table}` has {data['record_count']} records and columns: {col_names}.")
            for fk in data["foreign_keys"]:
                lines.append(
                    f"- `{table}` foreign key: {fk['from_column']} -> "
                    f"{fk['referenced_table']}.{fk['to_column']} "
                    f"(ON DELETE {fk['on_delete']})."
                )
            if "CHECK" in data["create_sql"]:
                lines.append(f"- `{table}` declares CHECK constraints in its CREATE TABLE statement.")
        redacted_cols = sorted(SENSITIVE_COLUMNS)
        if redacted_cols:
            lines.append(f"- Sample values for columns {', '.join(redacted_cols)} were redacted before being sent to the model or written to this report.")

    elif mode == "endpoints":
        for ep in evidence["endpoints"]:
            if ep["reachable"]:
                body = ep["response_json"]
                count = len(body) if isinstance(body, list) else (
                    len(body.get("products", body.get("suppliers", []))) if isinstance(body, dict) else "unknown"
                )
                lines.append(f"- {ep['name']} ({ep['url']}) returned status {ep['status_code']} with {count} record(s).")
            else:
                lines.append(f"- {ep['name']} ({ep['url']}) was not reachable: {ep['reachability_note']}")

    findings = ["FINDINGS"]
    if mode == "architecture":
        vc = evidence["verified_checks"]
        if vc["missing_files"]:
            findings.append(f"- Missing configured file(s): {', '.join(vc['missing_files'])}. Severity: Medium.")
        else:
            findings.append("- All configured architecture files were present. No High or Medium defect is shown by this evidence.")
        if vc["truncated_files"]:
            findings.append(f"- Evidence limitation: {len(vc['truncated_files'])} file excerpt(s) were truncated; the static review cannot prove uncollected code beyond the excerpt.")
    elif mode == "database":
        short_tables = [t for t, d in evidence["tables"].items() if d["record_count"] < 10 and t in ("products", "suppliers")]
        if short_tables:
            for t in short_tables:
                findings.append(f"- `{t}` has fewer than 10 records ({evidence['tables'][t]['record_count']}). Severity: Low (data issue, not a structural defect).")
        else:
            findings.append("- No High or Medium database defect is shown by the collected schema and count evidence.")
        findings.append(f"- Low evidence limitation: only {MAX_SAMPLE_ROWS} sample records per table were collected, so complete value validity was not established.")
    elif mode == "endpoints":
        unreachable = [ep for ep in evidence["endpoints"] if not ep["reachable"]]
        if unreachable:
            for ep in unreachable:
                findings.append(f"- {ep['name']} could not be reached. This is a deployment/runtime condition, not a proven source-code defect. Severity: Low.")
        else:
            findings.append("- All configured endpoints were reachable and returned a response. No defect is shown by this evidence alone.")

    recommendations = ["RECOMMENDATIONS"]
    if mode == "architecture":
        recommendations.append("- Address any missing configured files and rerun the focused automated tests.")
    elif mode == "database":
        recommendations.append("- Preserve the observed schema constraints and record-count tests.")
        if short_tables:
            recommendations.append("- Add seed rows so products and suppliers each reach at least 10 records.")
    elif mode == "endpoints":
        recommendations.append("- Ensure the backend container is running before relying on this evidence.")
        recommendations.append("- Keep this GET-only evidence separate from any write-path (POST/PUT/DELETE) testing.")

    adaptation = ["ADAPTATION APPLIED"]
    if grounding_issues:
        adaptation.append("- Replaced unsupported model claims with a deterministic summary of the collected evidence.")
        adaptation.append(f"- Grounding issues removed: {'; '.join(grounding_issues)}")
    else:
        adaptation.append("- No grounding issues were found; the deterministic summary supplements the model's review as-is.")

    return "\n".join(lines) + "\n\n" + "\n".join(findings) + "\n\n" + "\n".join(recommendations) + "\n\n" + "\n".join(adaptation)


# --------------------------------------------------------------------------
# Markdown report writer
# --------------------------------------------------------------------------

def write_report(mode: str, config: dict[str, Any], evidence: dict[str, Any],
                  initial_review: str, grounding_issues: list[str], final_review: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    filename_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    decision = "ADAPT" if grounding_issues else "PASS"

    plan_text = {
        "architecture": "Load the feature-specific prompt, collect read-only architecture evidence, "
                         "request an initial review, evaluate that review, and adapt it when required.",
        "database": "Load the feature-specific prompt, collect read-only database evidence, "
                    "request an initial review, evaluate that review, and adapt it when required.",
        "endpoints": "Load the feature-specific prompt, verify service reachability, collect read-only "
                     "GET evidence, request an initial review, evaluate that review, and adapt it when required.",
    }[mode]

    reviewer_feedback = f"DECISION: {decision}\n"
    if grounding_issues:
        reviewer_feedback += "Deterministic evidence checks found:\n"
        for issue in grounding_issues:
            reviewer_feedback += f"- {issue}\n"
    else:
        reviewer_feedback += "No deterministic grounding issues were found in the model's initial review.\n"

    report = f"""# Agentic Review Evidence

- Feature: {config['feature_name']}
- Contributor: Ryan Nolan
- Mode: {mode}
- Model: {OLLAMA_MODEL}
- Generated: {timestamp}
- Prompt: {SCRIPT_DIR / config['mode_prompt_files'][mode]}

## Plan

{plan_text}

## Evidence

```json
{json.dumps(evidence, indent=2, default=str)}
```

## Initial Review

{initial_review}

## Reviewer Feedback

{reviewer_feedback}
## Final Review

{final_review}
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"Ryan-inventory-{mode}-{filename_timestamp}.md"
    output_path.write_text(report, encoding="utf-8")
    return output_path


# --------------------------------------------------------------------------
# Mode orchestration
# --------------------------------------------------------------------------

def run_mode(mode: str, config: dict[str, Any]) -> Path:
    system_context = load_prompt(config["prompt_file"])
    mode_prompt = load_prompt(config["mode_prompt_files"][mode])

    if mode == "architecture":
        evidence = collect_architecture_evidence(config)
    elif mode == "database":
        evidence = collect_database_evidence(config)
    elif mode == "endpoints":
        evidence = collect_endpoints_evidence(config)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    initial_review = call_ollama(system_context, mode_prompt, evidence)
    grounding_issues = GROUNDING_CHECKS[mode](initial_review, evidence)
    final_review = build_final_review(mode, evidence, grounding_issues)

    return write_report(mode, config, evidence, initial_review, grounding_issues, final_review)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("architecture", "database", "endpoints", "all"):
        print("Usage: python3 agentic_review.py [architecture|database|endpoints|all]")
        raise SystemExit(1)

    config = load_config()
    modes = ["architecture", "database", "endpoints"] if sys.argv[1] == "all" else [sys.argv[1]]

    for mode in modes:
        print(f"Running {mode} review...")
        try:
            path = run_mode(mode, config)
            print(f"  -> wrote {path}")
        except SystemExit as exc:
            print(f"  -> stopped: {exc}")


if __name__ == "__main__":
    main()