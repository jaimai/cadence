from app.connectors.base import Connector
from app.connectors.facebook import FacebookConnector
from app.connectors.instagram import InstagramConnector
from app.connectors.tiktok import TikTokConnector

# Platforms the product targets. Those without a connector yet show as "bientôt".
PLATFORMS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
}

_registry: dict[str, Connector] = {
    "facebook": FacebookConnector(),
    "instagram": InstagramConnector(),
    "tiktok": TikTokConnector(),
}


def get_connector(platform: str) -> Connector | None:
    return _registry.get(platform)


def set_connector(platform: str, connector: Connector) -> None:
    """Swap a connector (tests)."""
    _registry[platform] = connector
