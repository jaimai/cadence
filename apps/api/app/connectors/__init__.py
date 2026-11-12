from app.connectors.base import Connector
from app.connectors.facebook import FacebookConnector
from app.connectors.instagram import InstagramConnector
from app.connectors.linkedin import LinkedInConnector
from app.connectors.tiktok import TikTokConnector
from app.connectors.x import XConnector

PLATFORMS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "tiktok": "TikTok",
    "x": "X",
}

_registry: dict[str, Connector] = {
    "facebook": FacebookConnector(),
    "instagram": InstagramConnector(),
    "linkedin": LinkedInConnector(),
    "tiktok": TikTokConnector(),
    "x": XConnector(),
}


def get_connector(platform: str) -> Connector | None:
    return _registry.get(platform)


def set_connector(platform: str, connector: Connector) -> None:
    """Swap a connector (tests)."""
    _registry[platform] = connector
