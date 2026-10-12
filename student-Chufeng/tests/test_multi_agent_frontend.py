"""Focused static checks for Chufeng's Multi-Agent review page."""

from html.parser import HTMLParser
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "frontend"


class PageAuditParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag == "a" and "href" in attributes:
            self.links.append(attributes["href"])
        if tag == "script" and "src" in attributes:
            self.scripts.append(attributes["src"])


def _parse_page(name):
    parser = PageAuditParser()
    parser.feed((FRONTEND_ROOT / name).read_text(encoding="utf-8"))
    return parser


def test_catalogue_has_multi_agent_entry_point():
    assert "multi-agent-assistant.html" in _parse_page("index.html").links


def test_multi_agent_page_has_unique_ids_and_complete_review_flow():
    page = _parse_page("multi-agent-assistant.html")

    assert len(page.ids) == len(set(page.ids))
    assert "index.html" in page.links
    assert "js/multi-agent-tools.js?v=1" in page.scripts
    for required_id in {
        "multiAgentStatusTitle",
        "multiAgentWorkflowForm",
        "multiAgentProductSelect",
        "loadLatestWorkflowButton",
        "multiAgentResultSection",
        "multiAgentAgentGrid",
        "multiAgentEvidenceList",
        "multiAgentReviewForm",
        "multiAgentRawOutput",
        "multiAgentHistoryList",
    }:
        assert required_id in page.ids


def test_multi_agent_frontend_uses_backend_and_authenticated_requests():
    script = (FRONTEND_ROOT / "js" / "multi-agent-tools.js").read_text(
        encoding="utf-8"
    )

    assert "http://localhost:5000/api/chufeng/multi-agent" in script
    assert '`${MULTI_AGENT_API_ROOT}/status`' in script
    assert '`${MULTI_AGENT_API_ROOT}/workflows`' in script
    assert 'credentials: "include"' in script
    assert "5004" not in script
    assert "http://127.0.0.1" not in script


def test_multi_agent_creation_keeps_evidence_server_side():
    script = (FRONTEND_ROOT / "js" / "multi-agent-tools.js").read_text(
        encoding="utf-8"
    )

    assert "const body = { question };" in script
    assert "body.product_id = Number(productIdText);" in script
    assert "body.feature" not in script
    assert "body.evidence" not in script


def test_multi_agent_page_exposes_agents_evidence_and_human_review():
    page = (FRONTEND_ROOT / "multi-agent-assistant.html").read_text(
        encoding="utf-8"
    )
    script = (FRONTEND_ROOT / "js" / "multi-agent-tools.js").read_text(
        encoding="utf-8"
    )

    for label in {"Planner", "Worker", "Reviewer", "Human"}:
        assert label in page
    for decision in {"accept", "partially_accept", "reject"}:
        assert f'value="{decision}"' in page
    assert "workflow.request?.evidence" in script
    assert "workflow.human_review" in script
    assert '`${MULTI_AGENT_WORKFLOWS_URL}/${encodeURIComponent(activeWorkflowId)}/review`' in script
    assert "loadHistory" in script
