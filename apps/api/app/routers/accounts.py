import html
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.connectors import PLATFORMS, get_connector
from app.connectors.base import ConnectorError
from app.deps import CurrentAuth, Session
from app.models import OAuthLink
from app.schemas import AccountOut
from app.security import create_oauth_state, read_oauth_state
from app.services import accounts as svc

router = APIRouter(prefix="/api", tags=["accounts"])


def _redirect_uri(platform: str) -> str:
    return f"{get_settings().api_base_url.rstrip('/')}/api/oauth/{platform}/callback"


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(
        f"{get_settings().web_base_url.rstrip('/')}/accounts?{urlencode(params)}"
    )


LINK_TTL = timedelta(minutes=15)

_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Cadence</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;min-height:100vh;display:flex;
align-items:center;justify-content:center;background:#f8fafc;color:#0f172a}}
main{{max-width:22rem;padding:2rem;text-align:center}}
.i{{width:3.5rem;height:3.5rem;border-radius:50%;margin:0 auto 1rem;display:flex;
align-items:center;justify-content:center;font-size:1.75rem;color:#fff;background:{color}}}
h1{{font-size:1.25rem;margin:0 0 .5rem}}p{{color:#64748b;margin:0;line-height:1.5}}</style>
</head><body><main><div class="i">{icon}</div><h1>{title}</h1><p>{text}</p></main></body></html>"""


def _page(ok: bool, title: str, text: str, status: int = 200) -> HTMLResponse:
    """Result screen for the phone: it is not signed in, so it cannot open the app."""
    return HTMLResponse(
        _PAGE.format(
            color="#10b981" if ok else "#ef4444",
            icon="✓" if ok else "!",
            title=html.escape(title),
            text=html.escape(text),
        ),
        status_code=status,
    )


def _require_connector(platform: str):
    connector = get_connector(platform)
    if connector is None:
        raise HTTPException(404, "Plateforme pas encore disponible.")
    if not connector.configured:
        raise HTTPException(
            400, f"Les identifiants de l'app {connector.label} ne sont pas configurés."
        )
    return connector


@router.get("/platforms")
async def platforms(auth: CurrentAuth) -> list[dict]:
    out = []
    for key, label in PLATFORMS.items():
        connector = get_connector(key)
        out.append(
            {
                "platform": key,
                "label": label,
                "available": connector is not None,
                "configured": bool(connector and connector.configured),
            }
        )
    return out


@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(auth: CurrentAuth, session: Session):
    return await svc.list_accounts(session, auth.workspace_id)


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect(account_id: uuid.UUID, auth: CurrentAuth, session: Session) -> None:
    account = await svc.get_account(session, auth.workspace_id, account_id)
    await session.delete(account)
    await session.commit()


@router.get("/oauth/{platform}/start")
async def oauth_start(platform: str, auth: CurrentAuth) -> dict:
    connector = _require_connector(platform)
    state = create_oauth_state(auth.workspace_id, platform)
    return {"url": connector.authorize_url(state, _redirect_uri(platform))}


@router.post("/oauth/{platform}/link")
async def oauth_link(platform: str, auth: CurrentAuth, session: Session) -> dict:
    """Link to scan with a phone, where switching between accounts is easier."""
    _require_connector(platform)
    link = OAuthLink(
        token=secrets.token_urlsafe(16),
        workspace_id=auth.workspace_id,
        platform=platform,
        expires_at=datetime.now(UTC) + LINK_TTL,
    )
    session.add(link)
    await session.commit()
    api = get_settings().api_base_url.rstrip("/")
    return {
        "url": f"{api}/api/oauth/go/{link.token}",
        "expires_at": link.expires_at,
        # A phone cannot open a link that points at this machine.
        "reachable": urlparse(api).hostname not in ("localhost", "127.0.0.1"),
    }


@router.get("/oauth/go/{token}")
async def oauth_go(token: str, session: Session):
    """Public: the phone has no session. The token stands for the workspace."""
    link = await session.get(OAuthLink, token)
    connector = get_connector(link.platform) if link else None
    if link is None or connector is None or link.expires_at < datetime.now(UTC):
        return _page(
            False, "Lien expiré", "Affiche un nouveau QR code dans Cadence et scanne-le.", 410
        )
    state = create_oauth_state(link.workspace_id, link.platform, via_link=True)
    return RedirectResponse(connector.authorize_url(state, _redirect_uri(link.platform)))


@router.get("/oauth/{platform}/callback")
async def oauth_callback(
    platform: str,
    session: Session,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    connector = get_connector(platform)
    decoded = read_oauth_state(state, platform) if state else None
    if connector is None or decoded is None:
        return _back(error="Lien de connexion expiré, recommence.")
    workspace_id, via_link = decoded

    def fail(message: str):
        return _page(False, "Connexion impossible", message) if via_link else _back(error=message)

    if error or not code:
        return fail("Connexion annulée.")
    try:
        connected = await connector.exchange_code(code, _redirect_uri(platform))
    except ConnectorError as e:
        return fail(str(e))
    if not connected:
        return fail(f"Aucun compte {connector.label} à connecter n'a été trouvé.")
    count = await svc.upsert_accounts(session, workspace_id, platform, connected)
    if via_link:
        names = ", ".join(c.display_name for c in connected)
        return _page(
            True,
            f"{names} connecté" if count == 1 else f"{count} comptes connectés",
            "Tu peux revenir sur ton ordinateur. Pour ajouter un autre compte, "
            "change de compte puis scanne à nouveau le QR code.",
        )
    return _back(connected=str(count))
