"""Compatibility adapter for Product Catalogue Multi-Agent callers."""

from shared.multi_agent_client import (
    DEFAULT_MULTI_AGENT_CLIENT_TIMEOUT_SECONDS,
    DEFAULT_MULTI_AGENT_SERVER_URL,
    MultiAgentClient,
    MultiAgentClientError,
    MultiAgentClientSettings,
    MultiAgentConfigurationError,
    MultiAgentDisabledError,
)

CHUFENG_FEATURE = "product_catalogue"


class ChufengMultiAgentClient(MultiAgentClient):
    def __init__(self, settings=None, *, http_request=None):
        super().__init__(CHUFENG_FEATURE, settings, http_request=http_request)
