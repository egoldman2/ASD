# Agentic Review Evidence

- Feature: Ethan Ting - Customer Accounts and Loyalty
- Contributor: Not specified
- Mode: mcp
- Model: llama3.1:8b
- Generated: 2026-09-30T09:58:09
- Prompt: /Users/ethan/Desktop/Uni/Advanced software development/Assessment 1/ASD/student-Ethan Ting/agentic/review_prompt.txt

## Plan

Load the feature-specific prompt, collect read-only mcp evidence, request an initial
review, evaluate that review, and adapt it when required.

## Evidence

```json
{
  "project_root": "/Users/ethan/Desktop/Uni/Advanced software development/Assessment 1/ASD",
  "read_only": true,
  "files": [
    {
      "path": "ai-services/mcp_server/server.py",
      "characters": 9305,
      "truncated": true,
      "content": "\"\"\"Shared local MCP server for the ASD marketplace application.\"\"\"\n\nfrom __future__ import annotations\n\nimport logging\nfrom typing import Any, cast\n\nfrom mcp.server.fastmcp import FastMCP\nfrom mcp.server.transport_security import TransportSecuritySettings\nfrom mcp.types import ToolAnnotations\nfrom starlette.requests import Request\nfrom starlette.responses import JSONResponse\n\nfrom mcp_server.confi"
    },
    {
      "path": "ai-services/mcp_server/tools/ethan_ting_customer.py",
      "characters": 1676,
      "truncated": true,
      "content": "\"\"\"Read-only, customer-safe MCP tools for Ethan Ting's loyalty feature.\n\nThis first tool calculates a tier from a supplied points balance. It does not\nlook up customers or expose account records from the unauthenticated local MCP\nservice. The thresholds match the customer database service's loyalty rules.\n\"\"\"\n\nfrom __future__ import annotations\n\nfrom typing import Any\n\nfrom mcp_server.response imp"
    },
    {
      "path": "shared/mcp_client.py",
      "characters": 10530,
      "truncated": true,
      "content": "\"\"\"Shared MCP transport; each feature supplies its own tool allowlist.\"\"\"\n\nfrom __future__ import annotations\n\nimport asyncio\nfrom collections.abc import Mapping\nfrom contextlib import asynccontextmanager\nfrom dataclasses import dataclass\nfrom datetime import timedelta\nimport math\nimport os\nfrom typing import Any, Callable, Coroutine, TypeVar\nfrom urllib.parse import urlparse\n\nimport httpx\nfrom mc"
    },
    {
      "path": "student-Ethan Ting/backend/app.py",
      "characters": 48951,
      "truncated": true,
      "content": "import asyncio\nimport json\nimport os\nfrom datetime import timedelta\nfrom functools import wraps\nfrom pathlib import Path\nimport re\nfrom urllib.error import HTTPError, URLError\nfrom urllib.parse import urlencode\nfrom urllib.request import Request as URLRequest\nfrom urllib.request import urlopen\n\nimport httpx\nfrom flask import Flask, g, jsonify, request, session\nfrom mcp import ClientSession\nfrom mc"
    },
    {
      "path": "student-Ethan Ting/frontend/js/admin-loyalty.js",
      "characters": 11142,
      "truncated": true,
      "content": "const AUTH_API_URL = \"http://localhost:6002\";\n\nconst loyaltyTableBody = document.querySelector(\"#loyaltyTableBody\");\nconst loyaltySearch = document.querySelector(\"#loyaltySearch\");\nconst loyaltyMessage = document.querySelector(\"#loyaltyMessage\");\nconst loyaltyAdjustmentPanel = document.querySelector(\"#loyaltyAdjustmentPanel\");\nconst loyaltyAdjustmentForm = document.querySelector(\"#loyaltyAdjustmen"
    },
    {
      "path": "student-Ethan Ting/tests/test_mcp_loyalty.py",
      "characters": 6593,
      "truncated": true,
      "content": "\"\"\"Backend boundary tests for Ethan Ting's loyalty MCP integration.\"\"\"\n\nimport importlib.util\nfrom pathlib import Path\n\nimport pytest\n\n\nBACKEND_APP = Path(__file__).resolve().parents[1] / \"backend\" / \"app.py\"\n\n\n@pytest.fixture\ndef auth_module():\n    specification = importlib.util.spec_from_file_location(\n        \"ethan_mcp_loyalty_app\", BACKEND_APP\n    )\n    module = importlib.util.module_from_spe"
    },
    {
      "path": "docker-compose.yml",
      "characters": 8596,
      "truncated": true,
      "content": "services:\n  shared-home:\n    image: nginx:1.27-alpine\n    ports:\n      - \"8000:80\"\n    volumes:\n      - ./shared:/usr/share/nginx/html:ro\n      - ./shared/nginx/home.conf:/etc/nginx/conf.d/default.conf:ro\n\n  product-catalogue:\n    build:\n      context: .\n      dockerfile: student-Chufeng/Dockerfile\n      target: frontend\n    ports:\n      - \"8001:80\"\n    volumes:\n      - ./shared/nginx/product-cata"
    },
    {
      "path": ".github/workflows/student-3.yml",
      "characters": 7068,
      "truncated": true,
      "content": "name: Ethan Ting - Customer Accounts and Loyalty CI\n\non:\n  push:\n    branches:\n      - main\n      - Ethan_Ting\n    paths:\n      - \"student-Ethan Ting/**\"\n      - \"ai-services/mcp_server/**\"\n      - \"ai-services/rag_server/**\"\n      - \"ai-services/agentic_loop.py\"\n      - \"ai-services/mcp_validation.py\"\n      - \"ai-services/rag_validation.py\"\n      - \"shared/**\"\n      - \"app.py\"\n      - \"docker-com"
    }
  ],
  "verified_checks": {
    "configured_files": 8,
    "present_files": 8,
    "missing_files": [],
    "truncated_files": [
      "ai-services/mcp_server/server.py",
      "ai-services/mcp_server/tools/ethan_ting_customer.py",
      "shared/mcp_client.py",
      "student-Ethan Ting/backend/app.py",
      "student-Ethan Ting/frontend/js/admin-loyalty.js",
      "student-Ethan Ting/tests/test_mcp_loyalty.py",
      "docker-compose.yml",
      ".github/workflows/student-3.yml"
    ],
    "source_checks": {},
    "required_tools": [
      "ethan_ting_calculate_loyalty_tier"
    ],
    "required_tool_count": 1,
    "definition_tool_names": [
      "chufeng_calculate_cart_summary",
      "chufeng_check_product_stock",
      "chufeng_get_product_details",
      "chufeng_search_products",
      "ethan_goldman_get_queue_summary",
      "ethan_goldman_get_ticket_context",
      "ethan_goldman_get_tickets_needing_attention",
      "ethan_goldman_search_tickets",
      "ethan_ting_calculate_loyalty_tier",
      "ryan_calculate_restock_order",
      "ryan_get_low_stock_items",
      "ryan_get_product_inventory",
      "ryan_get_supplier_details"
    ],
    "all_required_tools_registered": true,
    "all_required_tools_allowlisted": true,
    "read_only_annotations_present": true,
    "mcp_server_not_in_compose": true,
    "frontend_uses_backend_mcp_routes": true
  },
  "runtime": {
    "attempted": true,
    "available": true,
    "server_url": "http://127.0.0.1:8765/mcp",
    "tools": [
      {
        "name": "ethan_ting_calculate_loyalty_tier",
        "title": "Calculate Loyalty Tier",
        "description": "Calculate the Bronze, Silver, or Gold loyalty tier and points needed for the next tier from a supplied non-negative points balance. This tool is read-only and does not access customer data.",
        "input_schema": {
          "properties": {
            "points_balance": {
              "title": "Points Balance",
              "type": "integer"
            }
          },
          "required": [
            "points_balance"
          ],
          "title": "calculate_loyalty_tierArguments",
          "type": "object"
        },
        "output_schema": {
          "additionalProperties": true,
          "title": "calculate_loyalty_tierDictOutput",
          "type": "object"
        },
        "annotations": {
          "readOnlyHint": true,
          "destructiveHint": false,
          "idempotentHint": true,
          "openWorldHint": false
        }
      }
    ],
    "tool_names": [
      "ethan_ting_calculate_loyalty_tier"
    ],
    "probes": [
      {
        "name": "bronze-zero",
        "tool": "ethan_ting_calculate_loyalty_tier",
        "arguments": {
          "points_balance": 0
        },
        "success": true,
        "read_only": true,
        "checks_passed": true,
        "response_tool": "ethan_ting_calculate_loyalty_tier",
        "checks": [
          {
            "path": "result.tier",
            "expected": "Bronze",
            "observed": "Bronze",
            "passed": true
          },
          {
            "path": "result.next_tier",
            "expected": "Silver",
            "observed": "Silver",
            "passed": true
          },
          {
            "path": "result.points_to_next_tier",
            "expected": 500,
            "observed": 500,
            "passed": true
          }
        ],
        "response_digest": "f276fde3cf73fbf8559ba440a13f507e412a39ca4be15db5756ed13e277aecd8"
      },
      {
        "name": "bronze-boundary",
        "tool": "ethan_ting_calculate_loyalty_tier",
        "arguments": {
          "points_balance": 499
        },
        "success": true,
        "read_only": true,
        "checks_passed": true,
        "response_tool": "ethan_ting_calculate_loyalty_tier",
        "checks": [
          {
            "path": "result.tier",
            "expected": "Bronze",
            "observed": "Bronze",
            "passed": true
          },
          {
            "path": "result.next_tier",
            "expected": "Silver",
            "observed": "Silver",
            "passed": true
          },
          {
            "path": "result.points_to_next_tier",
            "expected": 1,
            "observed": 1,
            "passed": true
          }
        ],
        "response_digest": "5df548944a4ffbdcf8115bc69a59d32e8ad3104336482927154fa5fc4da8b54f"
      },
      {
        "name": "silver-start",
        "tool": "ethan_ting_calculate_loyalty_tier",
        "arguments": {
          "points_balance": 500
        },
        "success": true,
        "read_only": true,
        "checks_passed": true,
        "response_tool": "ethan_ting_calculate_loyalty_tier",
        "checks": [
          {
            "path": "result.tier",
            "expected": "Silver",
            "observed": "Silver",
            "passed": true
          },
          {
            "path": "result.next_tier",
            "expected": "Gold",
            "observed": "Gold",
            "passed": true
          },
          {
            "path": "result.points_to_next_tier",
            "expected": 500,
            "observed": 500,
            "passed": true
          }
        ],
        "response_digest": "5e29ecd6ed7689209a7814105c85e526e2a7f5f71e71aa5db2c7ad44770aa452"
      },
      {
        "name": "silver-boundary",
        "tool": "ethan_ting_calculate_loyalty_tier",
        "arguments": {
          "points_balance": 999
        },
        "success": true,
        "read_only": true,
        "checks_passed": true,
        "response_tool": "ethan_ting_calculate_loyalty_tier",
        "checks": [
          {
            "path": "result.tier",
            "expected": "Silver",
            "observed": "Silver",
            "passed": true
          },
          {
            "path": "result.next_tier",
            "expected": "Gold",
            "observed": "Gold",
            "passed": true
          },
          {
            "path": "result.points_to_next_tier",
            "expected": 1,
            "observed": 1,
            "passed": true
          }
        ],
        "response_digest": "f355ddb44bb709ee4fc3527f40bc7778f4808cdeb63f31eabb12b5b2b9350ef4"
      },
      {
        "name": "gold-start",
        "tool": "ethan_ting_calculate_loyalty_tier",
        "arguments": {
          "points_balance": 1000
        },
        "success": true,
        "read_only": true,
        "checks_passed": true,
        "response_tool": "ethan_ting_calculate_loyalty_tier",
        "checks": [
          {
            "path": "result.tier",
            "expected": "Gold",
            "observed": "Gold",
            "passed": true
          },
          {
            "path": "result.next_tier",
            "expected": null,
            "observed": null,
            "passed": true
          },
          {
            "path": "result.points_to_next_tier",
            "expected": 0,
            "observed": 0,
            "passed": true
          }
        ],
        "response_digest": "3f2bf487ddec5ebf027f693f3ae98b15700cd3b30d278d7e109e439c5e84c5c5"
      }
    ],
    "assistant_probes": [],
    "required_tools_discovered": true,
    "probe_complete": true,
    "all_required_tools_probed": true,
    "assistant_verified": false
  }
}
```

## Initial Review

**PLAN REVIEWED**

The reviewed plan is for Ethan Ting's Customer Accounts and Loyalty feature, which includes registering customer accounts, authenticating customers and administrators, storing passwords securely, allowing customers to view and update their own information, and enabling administrators to manage customer accounts.

**OBSERVATIONS**

* The MCP tool implementation is in `ai-services/mcp_server/tools/ethan_ting_customer.py`.
* The backend route for the MCP tool is not explicitly mentioned.
* The frontend request for the MCP tool is made through JavaScript code in `student-Ethan Ting/frontend/js/admin-loyalty.js`.

**FINDINGS**

1. **High**: There are no checks to prevent zero-value adjustments, excessive adjustments, or balances below zero (Severity: High).
	* Evidence: No specific evidence of threshold probes for these conditions.
2. **Medium**: The MCP tool implementation does not handle cases where the customer's loyalty balance is null or undefined (Severity: Medium).
	* Evidence: `ethan_ting_customer.py` assumes a valid points_balance argument.

**RECOMMENDATIONS**

1. Implement checks to prevent zero-value adjustments, excessive adjustments, and balances below zero.
2. Add error handling in the MCP tool implementation for cases where the customer's loyalty balance is null or undefined.

**PROPOSED ADAPTATION**

To address these findings, we can add threshold probes to check for invalid points values (e.g., 0) and implement checks within `ethan_ting_customer.py` to handle edge cases with missing or null loyalty balances.

## Reviewer Feedback

DECISION: ADAPT
Deterministic evidence checks found:
- The MCP response names fewer than two configured required tools and is too vague to validate their boundaries.
- The mcp response cites fewer than three configured files and is too narrow for the selected review.

Model reviewer feedback:
**DECISION: ADAPT**

REVIEW FEEDBACK:

1. The review is evidence-based but lacks specificity in some areas.

* Observation 2 should be more precise about the MCP tool implementation's assumption of a valid points_balance argument, citing specific lines or functions from `ethan_ting_customer.py`.
* Finding 1 could benefit from explicit mention of which threshold probes are missing for zero-value adjustments and excessive adjustments.
* Recommendation 1 is vague; instead, suggest adding specific probe names (e.g., "zero-adjustment") to check these conditions.

2. The review correctly identifies the need for error handling in `ethan_ting_customer.py` but could provide more context about how this would be implemented.

3. Adaptation suggestions are helpful and directly address the findings mentioned, making them useful additions to the original plan.

4. Review prose is clear and concise; however, some sentences could benefit from minor rewording for better clarity (e.g., "The MCP tool implementation does not handle cases where..." becomes more specific with a direct reference to `ethan_ting_customer.py`).

5. The review correctly follows the deterministic grounding rules by relying on verified evidence in the digest and avoiding unsupported claims.

6. Remaining limitations mentioned at the end of the original plan should be considered when interpreting this first review's findings, as they may impact the scope or accuracy of certain observations.

## Final Review

OBSERVATIONS
- 8 of 8 configured MCP files were present.
- Required tools configured: ethan_ting_calculate_loyalty_tier.
- All required tools appear in the shared server registration: True.
- All required tools appear in the selected feature backend allowlist: True.
- Read-only, non-destructive, structured-output annotations are present: True.
- No MCP server service is defined in Docker Compose: True.
- The frontend-to-backend MCP route markers are present: True.
- Live MCP validation available: True; attempted: True.
- Source evidence: `ai-services/mcp_server/server.py`; present: True; excerpt bounded: True.
- Source evidence: `ai-services/mcp_server/tools/ethan_ting_customer.py`; present: True; excerpt bounded: True.
- Source evidence: `shared/mcp_client.py`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/backend/app.py`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/frontend/js/admin-loyalty.js`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/tests/test_mcp_loyalty.py`; present: True; excerpt bounded: True.
- Source evidence: `docker-compose.yml`; present: True; excerpt bounded: True.
- Source evidence: `.github/workflows/student-3.yml`; present: True; excerpt bounded: True.
- Tools discovered through MCP: ethan_ting_calculate_loyalty_tier.
- Read-only probe result: {"name": "bronze-zero", "tool": "ethan_ting_calculate_loyalty_tier", "arguments": {"points_balance": 0}, "success": true, "read_only": true, "checks_passed": true, "response_tool": "ethan_ting_calculate_loyalty_tier", "checks": [{"path": "result.tier", "expected": "Bronze", "observed": "Bronze", "passed": true}, {"path": "result.next_tier", "expected": "Silver", "observed": "Silver", "passed": true}, {"path": "result.points_to_next_tier", "expected": 500, "observed": 500, "passed": true}], "response_digest": "f276fde3cf73fbf8559ba440a13f507e412a39ca4be15db5756ed13e277aecd8"}.
- Read-only probe result: {"name": "bronze-boundary", "tool": "ethan_ting_calculate_loyalty_tier", "arguments": {"points_balance": 499}, "success": true, "read_only": true, "checks_passed": true, "response_tool": "ethan_ting_calculate_loyalty_tier", "checks": [{"path": "result.tier", "expected": "Bronze", "observed": "Bronze", "passed": true}, {"path": "result.next_tier", "expected": "Silver", "observed": "Silver", "passed": true}, {"path": "result.points_to_next_tier", "expected": 1, "observed": 1, "passed": true}], "response_digest": "5df548944a4ffbdcf8115bc69a59d32e8ad3104336482927154fa5fc4da8b54f"}.
- Read-only probe result: {"name": "silver-start", "tool": "ethan_ting_calculate_loyalty_tier", "arguments": {"points_balance": 500}, "success": true, "read_only": true, "checks_passed": true, "response_tool": "ethan_ting_calculate_loyalty_tier", "checks": [{"path": "result.tier", "expected": "Silver", "observed": "Silver", "passed": true}, {"path": "result.next_tier", "expected": "Gold", "observed": "Gold", "passed": true}, {"path": "result.points_to_next_tier", "expected": 500, "observed": 500, "passed": true}], "response_digest": "5e29ecd6ed7689209a7814105c85e526e2a7f5f71e71aa5db2c7ad44770aa452"}.
- Read-only probe result: {"name": "silver-boundary", "tool": "ethan_ting_calculate_loyalty_tier", "arguments": {"points_balance": 999}, "success": true, "read_only": true, "checks_passed": true, "response_tool": "ethan_ting_calculate_loyalty_tier", "checks": [{"path": "result.tier", "expected": "Silver", "observed": "Silver", "passed": true}, {"path": "result.next_tier", "expected": "Gold", "observed": "Gold", "passed": true}, {"path": "result.points_to_next_tier", "expected": 1, "observed": 1, "passed": true}], "response_digest": "f355ddb44bb709ee4fc3527f40bc7778f4808cdeb63f31eabb12b5b2b9350ef4"}.
- Read-only probe result: {"name": "gold-start", "tool": "ethan_ting_calculate_loyalty_tier", "arguments": {"points_balance": 1000}, "success": true, "read_only": true, "checks_passed": true, "response_tool": "ethan_ting_calculate_loyalty_tier", "checks": [{"path": "result.tier", "expected": "Gold", "observed": "Gold", "passed": true}, {"path": "result.next_tier", "expected": null, "observed": null, "passed": true}, {"path": "result.points_to_next_tier", "expected": 0, "observed": 0, "passed": true}], "response_digest": "3f2bf487ddec5ebf027f693f3ae98b15700cd3b30d278d7e109e439c5e84c5c5"}.
- All configured probes passed: True; every required tool executed successfully: True; application AI assistant verified: False.

FINDINGS
- Evidence limitation: no complete successful application AI assistant validation was collected; review prose does not prove AI integration.

RECOMMENDATIONS
- Keep the MCP tools read-only, structured, owner-prefixed, and backend allowlisted.
- Retain focused protocol and tool-boundary tests as separate deterministic evidence.

ADAPTATION APPLIED
- Replaced unsupported model claims with a deterministic MCP evidence summary.
- Grounding issues removed: The MCP response names fewer than two configured required tools and is too vague to validate their boundaries.; The mcp response cites fewer than three configured files and is too narrow for the selected review.
