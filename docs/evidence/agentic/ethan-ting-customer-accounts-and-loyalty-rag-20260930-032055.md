# Agentic Review Evidence

- Feature: Ethan Ting - Customer Accounts and Loyalty
- Contributor: Not specified
- Mode: rag
- Model: llama3.1:8b
- Generated: 2026-09-30T03:20:55
- Prompt: /Users/ethan/Desktop/Uni/Advanced software development/Assessment 1/ASD/student-Ethan Ting/agentic/review_prompt.txt

## Plan

Load the feature-specific prompt, collect read-only rag evidence, request an initial
review, evaluate that review, and adapt it when required.

## Evidence

```json
{
  "project_root": "/Users/ethan/Desktop/Uni/Advanced software development/Assessment 1/ASD",
  "read_only": true,
  "files": [
    {
      "path": "ai-services/rag_server/rag_server.py",
      "characters": 5013,
      "truncated": true,
      "content": "\n\"\"\"MCP stdio entry point for the shared ASD marketplace RAG pipeline.\n\nThe MCP process deliberately uses stdio, matching the teaching example and\nallowing an MCP-capable AI client to launch it directly.  Dockerised project\nbackends use the separate HTTP adapter in :mod:`rag_http_server`.\n\"\"\"\n\nfrom __future__ import annotations\n\nimport logging\nfrom typing import Any, Callable, cast\n\nfrom mcp.serve"
    },
    {
      "path": "ai-services/rag_server/rag_pipeline.py",
      "characters": 37933,
      "truncated": true,
      "content": "\"\"\"Shared corpus refresh and deterministic vector indexing for local RAG.\"\"\"\n\nfrom __future__ import annotations\n\nfrom collections.abc import Mapping, Sequence\nfrom datetime import datetime, timezone\nimport hashlib\nfrom html import escape\nimport logging\nimport math\nimport re\nimport time\nfrom typing import Any\nfrom shared.feature_flags import feature_enabled\n\nimport chromadb\n\nfrom rag_server.config"
    },
    {
      "path": "ai-services/rag_server/sources/markdown_knowledge.py",
      "characters": 3505,
      "truncated": true,
      "content": "\"\"\"Bounded curated Markdown sources; no ticket data or client-chosen file paths.\"\"\"\n\nfrom hashlib import sha256\nfrom pathlib import Path\nimport re\nimport textwrap\n\nfrom .base import KnowledgeDocument, KnowledgeSource, SourceDataError, SourceUnavailableError\n\n\nMAX_FILE_BYTES = 64 * 1024\nMAX_FILES = 40\nMAX_CHUNKS = 200\nCHUNK_SIZE = 1000\n\n\nclass MarkdownKnowledgeSource(KnowledgeSource):\n    def __ini"
    },
    {
      "path": "ai-services/rag_server/knowledge/ethan_ting/accounts_and_loyalty.md",
      "characters": 2468,
      "truncated": true,
      "content": "# Customer accounts and loyalty: implemented guide\n\nThis guide describes the implemented ASD 2026 accounts and loyalty feature. It contains no customer records. For a live customer's details, use the protected account and loyalty screens, not this knowledge guide.\n\n## Customer registration\n\nCustomers can create their own account using a full name, email address, password and password confirmation."
    },
    {
      "path": "student-Ethan Ting/backend/app.py",
      "characters": 48951,
      "truncated": true,
      "content": "import asyncio\nimport json\nimport os\nfrom datetime import timedelta\nfrom functools import wraps\nfrom pathlib import Path\nimport re\nfrom urllib.error import HTTPError, URLError\nfrom urllib.parse import urlencode\nfrom urllib.request import Request as URLRequest\nfrom urllib.request import urlopen\n\nimport httpx\nfrom flask import Flask, g, jsonify, request, session\nfrom mcp import ClientSession\nfrom mc"
    },
    {
      "path": "student-Ethan Ting/frontend/js/admin.js",
      "characters": 21067,
      "truncated": true,
      "content": "const AUTH_API_URL = \"http://localhost:6002\";\n\nconst customerTableBody = document.querySelector(\"#customerTableBody\");\nconst administratorTableBody = document.querySelector(\"#administratorTableBody\");\nconst customerFormPanel = document.querySelector(\"#customerFormPanel\");\nconst customerForm = document.querySelector(\"#customerForm\");\nconst accountRoleInput = document.querySelector(\"#accountRole\");\n"
    },
    {
      "path": "student-Ethan Ting/tests/test_rag_accounts_loyalty.py",
      "characters": 6836,
      "truncated": true,
      "content": "\"\"\"Admin boundary tests for the accounts and loyalty RAG guide.\"\"\"\n\nimport importlib.util\nfrom pathlib import Path\n\nimport pytest\n\n\nAPP_PATH = Path(__file__).resolve().parents[1] / \"backend\" / \"app.py\"\nSCOPE = \"ethan_ting_accounts_loyalty\"\n\n\n@pytest.fixture\ndef backend(monkeypatch):\n    spec = importlib.util.spec_from_file_location(\"ethan_rag_app\", APP_PATH)\n    module = importlib.util.module_from"
    },
    {
      "path": "docker-compose.yml",
      "characters": 8216,
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
    "configured_files": 9,
    "present_files": 9,
    "missing_files": [],
    "truncated_files": [
      "ai-services/rag_server/rag_server.py",
      "ai-services/rag_server/rag_pipeline.py",
      "ai-services/rag_server/sources/markdown_knowledge.py",
      "ai-services/rag_server/knowledge/ethan_ting/accounts_and_loyalty.md",
      "student-Ethan Ting/backend/app.py",
      "student-Ethan Ting/frontend/js/admin.js",
      "student-Ethan Ting/tests/test_rag_accounts_loyalty.py",
      "docker-compose.yml",
      ".github/workflows/student-3.yml"
    ],
    "source_checks": {},
    "required_scope": "ethan_ting_accounts_loyalty",
    "required_operations": [
      "refresh_corpus",
      "retrieve_context",
      "answer_question"
    ],
    "all_required_operations_registered": true,
    "required_scope_registered": true,
    "grounding_controls_present": true,
    "rag_server_not_in_compose": true,
    "frontend_uses_backend_rag_routes": true,
    "configured_probe_count": 2
  },
  "runtime": {
    "attempted": true,
    "available": true,
    "server_url": "http://127.0.0.1:5003",
    "health_status": 200,
    "health": {
      "status": "healthy",
      "service": "asd-marketplace-rag",
      "enabled": true,
      "available_scopes": [
        "chufeng_catalogue",
        "ethan_goldman_support",
        "ethan_ting_accounts_loyalty"
      ],
      "operations": [
        "refresh_corpus",
        "retrieve_context",
        "answer_question"
      ],
      "ollama_model": "llama3.1:8b"
    },
    "probes": [
      {
        "name": "gold-threshold",
        "question": "How many loyalty points are needed for Gold?",
        "top_k": 5,
        "expected": "grounded",
        "attempted": true,
        "state": "grounded",
        "verified": true,
        "retrieval_status": 200,
        "retrieval": {
          "success": true,
          "operation": "retrieve_context",
          "data": {
            "query": "How many loyalty points are needed for Gold?",
            "scope": "ethan_ting_accounts_loyalty",
            "results": [
              {
                "rank": 1,
                "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
                "text": "Customer accounts and loyalty: implemented guide: Loyalty tiers\n\nCustomer loyalty balances start at zero points. Bronze covers 0 to 499 points. Silver covers 500 to 999 points. Gold begins at 1,000 points. Bronze customers reach Silver at 500 points; Silver customers reach Gold at 1,000 points. Gold has no next tier. The points needed for the next tier equal the next threshold minus the current balance.",
                "metadata": {
                  "section": "Loyalty tiers",
                  "curated": true,
                  "scope": "ethan_ting_accounts_loyalty",
                  "chunk_index": 3,
                  "revision": "723a5a4c5021d3767c6c5701e374d7354119f8de9b5238d4beeea2d262b4a147",
                  "source_file": "accounts_and_loyalty.md",
                  "citation_label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
                  "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md"
                },
                "distance": 0.533487,
                "relevance_score": 0.466513,
                "citation": {
                  "rank": 1,
                  "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
                  "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
                  "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
                  "scope": "ethan_ting_accounts_loyalty"
                }
              }
            ],
            "result_count": 1
          },
          "citations": [
            {
              "rank": 1,
              "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
              "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
              "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
              "scope": "ethan_ting_accounts_loyalty"
            }
          ],
          "confidence": "medium",
          "insufficient_context": false,
          "error": null,
          "metadata": {
            "requested_top_k": 5,
            "indexed_document_count": 6,
            "minimum_relevance_score": 0.25,
            "distance_metric": "cosine",
            "embedding": "deterministic_sha256",
            "embedding_dimensions": 256
          }
        },
        "retrieval_verified": true,
        "answer_status": 200,
        "answer": {
          "success": true,
          "operation": "answer_question",
          "data": {
            "question": "How many loyalty points are needed for Gold?",
            "scope": "ethan_ting_accounts_loyalty",
            "answer": "According to [1], Gold begins at 1,000 points.",
            "retrieved_count": 1,
            "model": "llama3.1:8b"
          },
          "citations": [
            {
              "rank": 1,
              "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
              "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
              "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
              "scope": "ethan_ting_accounts_loyalty"
            }
          ],
          "confidence": "medium",
          "insufficient_context": false,
          "error": null,
          "metadata": {
            "grounded": true,
            "model_invoked": true,
            "generation_attempts": 1,
            "context_characters": 660,
            "confidence_basis": "retrieval_similarity_not_probability_of_correctness",
            "requested_top_k": 5,
            "minimum_relevance_score": 0.25,
            "distance_metric": "cosine",
            "embedding": "deterministic_sha256"
          }
        },
        "checks": [],
        "generation_skipped": false
      },
      {
        "name": "unrelated-astronomy",
        "question": "quasar orbital spectroscopy wavelengths",
        "top_k": 5,
        "expected": "insufficient",
        "attempted": true,
        "state": "insufficient",
        "verified": true,
        "retrieval_status": 200,
        "retrieval": {
          "success": true,
          "operation": "retrieve_context",
          "data": {
            "query": "quasar orbital spectroscopy wavelengths",
            "scope": "ethan_ting_accounts_loyalty",
            "results": [],
            "result_count": 0,
            "message": "<redacted>"
          },
          "citations": [],
          "confidence": "insufficient",
          "insufficient_context": true,
          "error": null,
          "metadata": {
            "requested_top_k": 5,
            "indexed_document_count": 6,
            "minimum_relevance_score": 0.25
          }
        },
        "retrieval_verified": true,
        "answer_status": 200,
        "answer": {
          "success": true,
          "operation": "answer_question",
          "data": {
            "question": "quasar orbital spectroscopy wavelengths",
            "scope": "ethan_ting_accounts_loyalty",
            "answer": "Insufficient context to answer this question.",
            "retrieved_count": 0,
            "model": null
          },
          "citations": [],
          "confidence": "insufficient",
          "insufficient_context": true,
          "error": null,
          "metadata": {
            "grounded": true,
            "model_invoked": false,
            "minimum_relevance_score": 0.25
          }
        },
        "checks": [],
        "generation_skipped": true
      }
    ],
    "refresh": {
      "success": true,
      "operation": "refresh_corpus",
      "data": {
        "scope": "ethan_ting_accounts_loyalty",
        "source": "Ethan Ting Accounts and Loyalty",
        "document_count": 6,
        "added_count": 0,
        "updated_count": 6,
        "removed_count": 0,
        "collection": "asd_release1_shared_context",
        "collection_count": 6,
        "refreshed_at": "2026-09-29T17:19:32.742964+00:00"
      },
      "citations": [],
      "confidence": null,
      "insufficient_context": false,
      "error": null,
      "metadata": {
        "read_only_source": true,
        "embedding": "deterministic_sha256",
        "embedding_dimensions": 256
      }
    },
    "refresh_verified": true,
    "probe": {
      "name": "gold-threshold",
      "question": "How many loyalty points are needed for Gold?",
      "top_k": 5,
      "expected": "grounded",
      "attempted": true,
      "state": "grounded",
      "verified": true,
      "retrieval_status": 200,
      "retrieval": {
        "success": true,
        "operation": "retrieve_context",
        "data": {
          "query": "How many loyalty points are needed for Gold?",
          "scope": "ethan_ting_accounts_loyalty",
          "results": [
            {
              "rank": 1,
              "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
              "text": "Customer accounts and loyalty: implemented guide: Loyalty tiers\n\nCustomer loyalty balances start at zero points. Bronze covers 0 to 499 points. Silver covers 500 to 999 points. Gold begins at 1,000 points. Bronze customers reach Silver at 500 points; Silver customers reach Gold at 1,000 points. Gold has no next tier. The points needed for the next tier equal the next threshold minus the current balance.",
              "metadata": {
                "section": "Loyalty tiers",
                "curated": true,
                "scope": "ethan_ting_accounts_loyalty",
                "chunk_index": 3,
                "revision": "723a5a4c5021d3767c6c5701e374d7354119f8de9b5238d4beeea2d262b4a147",
                "source_file": "accounts_and_loyalty.md",
                "citation_label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
                "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md"
              },
              "distance": 0.533487,
              "relevance_score": 0.466513,
              "citation": {
                "rank": 1,
                "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
                "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
                "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
                "scope": "ethan_ting_accounts_loyalty"
              }
            }
          ],
          "result_count": 1
        },
        "citations": [
          {
            "rank": 1,
            "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
            "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
            "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
            "scope": "ethan_ting_accounts_loyalty"
          }
        ],
        "confidence": "medium",
        "insufficient_context": false,
        "error": null,
        "metadata": {
          "requested_top_k": 5,
          "indexed_document_count": 6,
          "minimum_relevance_score": 0.25,
          "distance_metric": "cosine",
          "embedding": "deterministic_sha256",
          "embedding_dimensions": 256
        }
      },
      "retrieval_verified": true,
      "answer_status": 200,
      "answer": {
        "success": true,
        "operation": "answer_question",
        "data": {
          "question": "How many loyalty points are needed for Gold?",
          "scope": "ethan_ting_accounts_loyalty",
          "answer": "According to [1], Gold begins at 1,000 points.",
          "retrieved_count": 1,
          "model": "llama3.1:8b"
        },
        "citations": [
          {
            "rank": 1,
            "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3",
            "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md",
            "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers",
            "scope": "ethan_ting_accounts_loyalty"
          }
        ],
        "confidence": "medium",
        "insufficient_context": false,
        "error": null,
        "metadata": {
          "grounded": true,
          "model_invoked": true,
          "generation_attempts": 1,
          "context_characters": 660,
          "confidence_basis": "retrieval_similarity_not_probability_of_correctness",
          "requested_top_k": 5,
          "minimum_relevance_score": 0.25,
          "distance_metric": "cosine",
          "embedding": "deterministic_sha256"
        }
      },
      "checks": [],
      "generation_skipped": false
    },
    "required_scope_available": true,
    "required_operations_available": true,
    "grounded_answer_verified": true,
    "insufficient_context_verified": true,
    "probe_complete": true,
    "validation_complete": true
  }
}
```

## Initial Review

**PLAN REVIEWED**

The reviewed plan is the RAG integration for Ethan Ting's Customer Accounts and Loyalty feature.

**OBSERVATIONS**

* The guide contains no live customer records, as intended by the privacy boundary (ai-services/rag_server/knowledge/ethan_ting/accounts_and_loyalty.md).
* The frontend uses backend RAG routes to retrieve answers from the MCP server.
* Two probes were attempted: "gold-threshold" and "unrelated-astronomy".
* Both probes had a retrieval status of 200, indicating successful data retrieval.

**FINDINGS**

1. **High**: No evidence shows that customer accounts are created with passwords hashed using Werkzeug (student-Ethan Ting/backend/app.py).
2. **Medium**: The frontend uses backend RAG routes to retrieve answers from the MCP server, but it is unclear if this integration is complete or functional (ai-services/rag_server/sources/markdown_knowledge.py).

**RECOMMENDATIONS**

1. Verify that passwords are hashed using Werkzeug in student-Ethan Ting/backend/app.py.
2. Investigate and document the frontend-backend RAG route integration to ensure its completeness and functionality.

**PROPOSED ADAPTATION**

To address these findings, review the backend code for password hashing (student-Ethan Ting/backend/app.py) and investigate the frontend-backend RAG route integration by examining ai-services/rag_server/sources/markdown_knowledge.py.

## Reviewer Feedback

DECISION: ADAPT
Deterministic evidence checks found:
- The RAG response omits the configured feature knowledge scope.
- The RAG response names fewer than two required operations and is too vague to validate the pipeline boundaries.

Model reviewer feedback:
**DECISION: PASS**

REVIEW FEEDBACK:

* The review is evidence-based as it cites specific file paths and code snippets from the provided evidence digest.
* It correctly scopes its findings to the RAG integration for Ethan Ting's Customer Accounts and Loyalty feature, adhering to the specified rules.
* However, some of the recommendations could be more specific. For instance, instead of "Verify that passwords are hashed using Werkzeug in student-Ethan Ting/backend/app.py," it would be better to say "Check if password hashing is implemented correctly by looking for a call to `Werkzeug.security.generate_password_hash` or similar function."
* The review does not mention the absence of live customer records as an issue, which aligns with the provided evidence and rules.
* Overall, this first review demonstrates good practice in following the specified rules and citing concrete evidence.

## Final Review

OBSERVATIONS
- 9 of 9 configured RAG files were present.
- Required knowledge scope: ethan_ting_accounts_loyalty.
- Required operations: refresh_corpus, retrieve_context, answer_question.
- All required operations appear in the shared RAG server: True.
- The required feature scope appears in the source and backend client: True.
- Grounding, citation validation, and insufficient-context controls are present: True.
- No RAG server service is defined in Docker Compose: True.
- The frontend-to-backend RAG route markers are present: True.
- Live RAG validation available: True; attempted: True.
- Source evidence: `ai-services/rag_server/rag_server.py`; present: True; excerpt bounded: True.
- Source evidence: `ai-services/rag_server/rag_pipeline.py`; present: True; excerpt bounded: True.
- Source evidence: `ai-services/rag_server/sources/markdown_knowledge.py`; present: True; excerpt bounded: True.
- Source evidence: `ai-services/rag_server/knowledge/ethan_ting/accounts_and_loyalty.md`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/backend/app.py`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/frontend/js/admin.js`; present: True; excerpt bounded: True.
- Source evidence: `student-Ethan Ting/tests/test_rag_accounts_loyalty.py`; present: True; excerpt bounded: True.
- Source evidence: `docker-compose.yml`; present: True; excerpt bounded: True.
- Source evidence: `.github/workflows/student-3.yml`; present: True; excerpt bounded: True.
- Live RAG health: {"status": "healthy", "service": "asd-marketplace-rag", "enabled": true, "available_scopes": ["chufeng_catalogue", "ethan_goldman_support", "ethan_ting_accounts_loyalty"], "operations": ["refresh_corpus", "retrieve_context", "answer_question"], "ollama_model": "llama3.1:8b"}.
- Bounded RAG probes: [{"name": "gold-threshold", "question": "How many loyalty points are needed for Gold?", "top_k": 5, "expected": "grounded", "attempted": true, "state": "grounded", "verified": true, "retrieval_status": 200, "retrieval_verified": true, "answer_status": 200, "checks": [], "generation_skipped": false, "model": "llama3.1:8b", "confidence": "medium", "model_invoked": true, "answer_excerpt": "According to [1], Gold begins at 1,000 points.", "citations": [{"rank": 1, "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3", "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md", "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers", "scope": "ethan_ting_accounts_loyalty"}], "passage_excerpts": [{"citation": {"rank": 1, "document_id": "ethan_ting_accounts_loyalty:accounts_and_loyalty.md:3", "source_id": "ethan_ting_accounts_loyalty/accounts_and_loyalty.md", "label": "Customer accounts and loyalty: implemented guide: Loyalty tiers", "scope": "ethan_ting_accounts_loyalty"}, "text": "Customer accounts and loyalty: implemented guide: Loyalty tiers\n\nCustomer loyalty balances start at zero points. Bronze covers 0 to 499 points. Silver covers 500 to 999 points. Gold begins at 1,000 points. Bronze customers reach Silver at 5"}], "passages_not_in_review": 0}, {"name": "unrelated-astronomy", "question": "quasar orbital spectroscopy wavelengths", "top_k": 5, "expected": "insufficient", "attempted": true, "state": "insufficient", "verified": true, "retrieval_status": 200, "retrieval_verified": true, "answer_status": 200, "checks": [], "generation_skipped": true, "model": null, "confidence": "insufficient", "model_invoked": false, "answer_excerpt": "Insufficient context to answer this question.", "citations": [], "passage_excerpts": [], "passages_not_in_review": 0}].
- Required scope available: True; required operations available: True.
- Grounded answer verified: True; complete probe: True; unsupported question without generation verified: True; complete validation: True.

FINDINGS
- The collected static and live RAG checks did not prove a grounding or integration defect.

RECOMMENDATIONS
- Keep the selected feature's approved knowledge sources authoritative and read-only.
- Keep citations, confidence, Top-K bounds, and insufficient-context handling visible.
- Retain focused RAG pipeline and backend integration tests as separate deterministic evidence.

ADAPTATION APPLIED
- Replaced unsupported model claims with a deterministic RAG evidence summary.
- Grounding issues removed: The RAG response omits the configured feature knowledge scope.; The RAG response names fewer than two required operations and is too vague to validate the pipeline boundaries.
