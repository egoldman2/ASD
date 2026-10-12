"""Command-line runner for one shared multi-agent workflow."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from json import JSONDecodeError
from pathlib import Path
import sys
from typing import Any, TextIO

from multi_agent_server.agents.planner_agent import PlannerResponseError
from multi_agent_server.agents.reviewer_agent import (
    ReviewerInputError,
    ReviewerResponseError,
)
from multi_agent_server.agents.worker_agent import (
    WorkerInputError,
    WorkerResponseError,
)
from multi_agent_server.app import build_coordinator
from multi_agent_server.config import (
    ConfigurationError,
    MultiAgentSettings,
    get_settings,
)
from multi_agent_server.contracts import (
    ContractValidationError,
    WorkflowRequest,
)
from multi_agent_server.coordinator import WorkflowCoordinator
from multi_agent_server.model_client import ModelClientError
from multi_agent_server.workflow_store import (
    WorkflowStateError,
    WorkflowStoreError,
)


EXIT_OK = 0
EXIT_INTERNAL_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_MODEL_ERROR = 3
EXIT_SERVICE_ERROR = 4

SettingsLoader = Callable[[], MultiAgentSettings]
CoordinatorFactory = Callable[[MultiAgentSettings], WorkflowCoordinator]


def build_parser() -> argparse.ArgumentParser:
    """Build the small, stable CLI accepted by the demonstration runner."""

    parser = argparse.ArgumentParser(
        prog="python -m multi_agent_server.workflow_runner",
        description=(
            "Run one Planner, Worker, and Reviewer workflow using evidence "
            "from a validated JSON request file."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        metavar="PATH",
        help="UTF-8 JSON file containing a WorkflowRequest.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the complete stored workflow as JSON.",
    )
    return parser


def load_workflow_request(path: Path | str) -> WorkflowRequest:
    """Read and validate one UTF-8 JSON workflow request."""

    input_path = Path(path)
    if input_path.exists() and not input_path.is_file():
        raise IsADirectoryError(str(input_path))
    text = input_path.read_text(encoding="utf-8")
    payload = json.loads(text)
    return WorkflowRequest.from_dict(payload)


def _write_error(stream: TextIO, code: str, message: str) -> None:
    print(f"ERROR [{code}]: {message}", file=stream)


def _write_human_result(
    stream: TextIO,
    result: dict[str, Any],
    workflow_request: WorkflowRequest,
    settings: MultiAgentSettings,
) -> None:
    planner = result["planner_result"]
    worker = result["worker_result"]
    reviewer = result["reviewer_result"]
    evidence_ids = ", ".join(
        item.evidence_id for item in workflow_request.evidence
    )
    lines = (
        "Multi-Agent workflow completed",
        f"Workflow ID: {result['workflow_id']}",
        f"Feature: {workflow_request.feature.value}",
        f"Status: {result['status']}",
        f"Evidence IDs: {evidence_ids}",
        f"Planner Model: {planner['model']}",
        "",
        "Planner Result:",
        planner["plan"],
        "",
        f"Worker Model: {worker['model']}",
        "Worker Result:",
        worker["output"],
        "",
        f"Reviewer Model: {reviewer['model']}",
        "Reviewer Result:",
        reviewer["review"],
        "",
        f"Workflow History: {settings.history_path}",
        f"Coordination Audit: {settings.audit_path}",
    )
    print("\n".join(lines), file=stream)


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings_loader: SettingsLoader = get_settings,
    coordinator_factory: CoordinatorFactory = build_coordinator,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute the CLI and return a stable process exit code."""

    output = stdout if stdout is not None else sys.stdout
    errors = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)

    try:
        workflow_request = load_workflow_request(args.input)
    except FileNotFoundError:
        _write_error(errors, "input_not_found", f"Input file not found: {args.input}")
        return EXIT_INPUT_ERROR
    except IsADirectoryError:
        _write_error(errors, "invalid_input_path", "Input path must be a JSON file.")
        return EXIT_INPUT_ERROR
    except UnicodeDecodeError:
        _write_error(errors, "invalid_encoding", "Input file must use UTF-8.")
        return EXIT_INPUT_ERROR
    except JSONDecodeError as error:
        _write_error(
            errors,
            "invalid_json",
            f"Input file contains invalid JSON at line {error.lineno}, "
            f"column {error.colno}.",
        )
        return EXIT_INPUT_ERROR
    except ContractValidationError as error:
        _write_error(
            errors,
            error.code,
            f"{error.field}: {error.message}",
        )
        return EXIT_INPUT_ERROR
    except OSError:
        _write_error(errors, "input_unavailable", "Input file could not be read.")
        return EXIT_INPUT_ERROR

    try:
        settings = settings_loader()
        coordinator = coordinator_factory(settings)
        result = coordinator.run(workflow_request)
    except ConfigurationError as error:
        _write_error(errors, "configuration_error", str(error))
        return EXIT_SERVICE_ERROR
    except ModelClientError as error:
        _write_error(errors, error.code, error.message)
        return EXIT_MODEL_ERROR
    except (
        PlannerResponseError,
        WorkerResponseError,
        ReviewerResponseError,
    ) as error:
        _write_error(errors, error.code, str(error))
        return EXIT_MODEL_ERROR
    except (WorkerInputError, ReviewerInputError, WorkflowStateError):
        _write_error(
            errors,
            "workflow_state_error",
            "The workflow produced inconsistent internal state.",
        )
        return EXIT_SERVICE_ERROR
    except WorkflowStoreError:
        _write_error(
            errors,
            "workflow_store_error",
            "Workflow persistence is unavailable.",
        )
        return EXIT_SERVICE_ERROR
    except Exception:
        _write_error(
            errors,
            "internal_error",
            "The Multi-Agent workflow could not be completed.",
        )
        return EXIT_INTERNAL_ERROR

    if args.json_output:
        json.dump(result, output, ensure_ascii=False, sort_keys=True, indent=2)
        output.write("\n")
    else:
        _write_human_result(output, result, workflow_request, settings)
    return EXIT_OK


def main() -> None:
    """Run the command-line workflow and terminate with its exit code."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
