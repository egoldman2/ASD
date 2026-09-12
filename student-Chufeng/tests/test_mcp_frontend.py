"""Static integration checks for Chufeng's MCP frontend page."""

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


def test_catalogue_has_mcp_assistant_entry_point():
    catalogue = _parse_page("index.html")

    assert "mcp-assistant.html" in catalogue.links


def test_mcp_page_has_unique_ids_and_expected_assets():
    page = _parse_page("mcp-assistant.html")

    assert len(page.ids) == len(set(page.ids))
    assert "index.html" in page.links
    assert "js/mcp-tools.js?v=1" in page.scripts
    for required_id in {
        "mcpStatusTitle",
        "searchToolForm",
        "detailsToolForm",
        "stockToolForm",
        "cartToolForm",
        "mcpResultSection",
        "mcpRequestOutput",
        "mcpResponseOutput",
    }:
        assert required_id in page.ids


def test_mcp_frontend_uses_backend_routes_not_direct_mcp_transport():
    script = (FRONTEND_ROOT / "js" / "mcp-tools.js").read_text(
        encoding="utf-8"
    )

    assert "http://localhost:5000/api/chufeng/mcp/status" in script
    assert "http://localhost:5000/api/chufeng/mcp/tools" in script
    assert "http://localhost:5000/api/chufeng/mcp/tools/call" in script
    assert "8765" not in script
    assert "http://127.0.0.1" not in script


def test_frontend_exposes_every_chufeng_tool():
    page = (FRONTEND_ROOT / "mcp-assistant.html").read_text(encoding="utf-8")

    for tool_name in {
        "chufeng_search_products",
        "chufeng_get_product_details",
        "chufeng_check_product_stock",
        "chufeng_calculate_cart_summary",
    }:
        assert f'data-mcp-tool="{tool_name}"' in page
