
"""Focused static checks for Chufeng's RAG demonstration page."""

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


def test_catalogue_has_rag_assistant_entry_point():
    assert "rag-assistant.html" in _parse_page("index.html").links


def test_rag_page_has_unique_ids_and_complete_demo_workflow():
    page = _parse_page("rag-assistant.html")

    assert len(page.ids) == len(set(page.ids))
    assert "index.html" in page.links
    assert "js/rag-tools.js?v=1" in page.scripts
    for required_id in {
        "ragModeToggle",
        "ragModeState",
        "ragStatusTitle",
        "refreshCorpusForm",
        "retrieveContextForm",
        "answerQuestionForm",
        "ragResultSection",
        "ragConfidenceBadge",
        "ragRequestOutput",
        "ragResponseOutput",
    }:
        assert required_id in page.ids


def test_rag_frontend_uses_chufeng_backend_not_direct_rag_server():
    script = (FRONTEND_ROOT / "js" / "rag-tools.js").read_text(
        encoding="utf-8"
    )

    assert "http://localhost:5000/api/chufeng/rag" in script
    assert '`${RAG_API_ROOT}/status`' in script
    assert '`${RAG_API_ROOT}/refresh`' in script
    assert '`${RAG_API_ROOT}/retrieve`' in script
    assert '`${RAG_API_ROOT}/answer`' in script
    assert "5003" not in script
    assert "http://127.0.0.1" not in script


def test_rag_mode_and_grounding_evidence_are_visible():
    page = (FRONTEND_ROOT / "rag-assistant.html").read_text(encoding="utf-8")
    script = (FRONTEND_ROOT / "js" / "rag-tools.js").read_text(
        encoding="utf-8"
    )

    assert 'max="20"' in page
    assert "Top K" in page
    assert "Answer with Citations" in page
    assert "chufeng_rag_mode_enabled" in script
    assert '"X-RAG-Mode"' in script
    assert "localStorage.setItem" in script
    assert "localStorage.getItem" in script
    assert "relevance_score" in script
    assert "source_id" in script
    assert "payload.confidence" in script
