"""MCP server: lets an LLM manage content with the same services as the web app.

Auth is a workspace API key sent as `Authorization: Bearer cad_...`.
"""

import uuid
from datetime import datetime
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.db import SessionLocal
from app.deps import workspace_for_api_key
from app.schemas import AccountOut, MediaOut, PostOut
from app.services import accounts as accounts_svc
from app.services import media as media_svc
from app.services import posts as posts_svc
from app.services.errors import DomainError

mcp = MCPServer(
    "cadence",
    instructions=(
        "Gestion de contenu pour réseaux sociaux. Commence par list_accounts pour obtenir "
        "les identifiants des comptes. Les médias doivent être importés avec "
        "import_media_from_url avant d'être attachés à un post. Les dates sont en ISO 8601 "
        "avec fuseau horaire. Selon le réglage de l'espace, un post que tu planifies peut "
        "rester en brouillon en attente de validation humaine : le champ `note` te le dit."
    ),
)


def _bearer(headers: Any) -> str | None:
    value = (headers or {}).get("authorization", "")
    scheme, _, token = value.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token else None


async def _workspace(ctx: Context) -> uuid.UUID:
    token = _bearer(ctx.headers)
    async with SessionLocal() as session:
        workspace_id = await workspace_for_api_key(session, token) if token else None
    if workspace_id is None:
        raise ToolError("Clé API invalide ou manquante.")
    return workspace_id


def _post(post, actor_held: bool = False) -> dict[str, Any]:
    out = PostOut.of(post).model_dump(mode="json")
    if actor_held:
        out["note"] = (
            "Enregistré en brouillon : l'espace exige une validation humaine avant "
            "publication. L'utilisateur doit l'approuver dans l'application."
        )
    return out


def _fail(e: DomainError) -> ToolError:
    """Anticipated failure: the message reaches the model so it can correct itself."""
    return ToolError(e.message)


def _id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise ToolError(f"Identifiant invalide : {value!r}.") from None


@mcp.tool()
async def list_accounts(ctx: Context) -> list[dict[str, Any]]:
    """Liste les comptes sociaux connectés (id, plateforme, nom, statut)."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        accounts = await accounts_svc.list_accounts(session, ws)
    return [AccountOut.model_validate(a).model_dump(mode="json") for a in accounts]


@mcp.tool()
async def list_media(ctx: Context) -> list[dict[str, Any]]:
    """Liste les médias (images, vidéos) disponibles dans la médiathèque."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        items = await media_svc.list_media(session, ws)
    return [MediaOut.of(m).model_dump(mode="json") for m in items]


@mcp.tool()
async def import_media_from_url(url: str, ctx: Context) -> dict[str, Any]:
    """Importe une image (JPG, PNG, WebP) ou une vidéo (MP4, MOV) depuis une URL publique.

    Retourne le média, dont l'id sert ensuite dans create_post ou update_post.
    """
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            media = await media_svc.import_from_url(session, ws, url)
        except DomainError as e:
            raise _fail(e) from None
    return MediaOut.of(media).model_dump(mode="json")


@mcp.tool()
async def create_post(
    ctx: Context,
    caption: str,
    account_ids: list[str],
    media_ids: list[str] | None = None,
    scheduled_at: datetime | None = None,
    publish_now: bool = False,
    caption_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Crée un post pour un ou plusieurs comptes.

    Sans scheduled_at ni publish_now, le post reste un brouillon.
    caption_overrides permet un texte différent par compte : {account_id: texte}.
    """
    ws = await _workspace(ctx)
    wants_publish = publish_now or scheduled_at is not None
    async with SessionLocal() as session:
        try:
            post = await posts_svc.create_post(
                session,
                ws,
                caption=caption,
                account_ids=[_id(a) for a in account_ids],
                media_ids=[_id(m) for m in media_ids or []],
                scheduled_at=scheduled_at,
                publish_now=publish_now,
                caption_overrides={_id(k): v for k, v in (caption_overrides or {}).items()},
                actor="mcp",
            )
        except DomainError as e:
            raise _fail(e) from None
    return _post(post, wants_publish and post.status == "draft")


@mcp.tool()
async def update_post(
    ctx: Context,
    post_id: str,
    caption: str | None = None,
    account_ids: list[str] | None = None,
    media_ids: list[str] | None = None,
    caption_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Modifie un brouillon ou un post planifié. Seuls les champs fournis changent."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            post = await posts_svc.get_post(session, ws, _id(post_id))
            post = await posts_svc.update_post(
                session,
                post,
                caption=caption,
                account_ids=[_id(a) for a in account_ids] if account_ids is not None else None,
                media_ids=[_id(m) for m in media_ids] if media_ids is not None else None,
                caption_overrides=(
                    {_id(k): v for k, v in caption_overrides.items()}
                    if caption_overrides is not None
                    else None
                ),
            )
        except DomainError as e:
            raise _fail(e) from None
    return _post(post)


@mcp.tool()
async def schedule_post(
    ctx: Context, post_id: str, scheduled_at: datetime | None = None
) -> dict[str, Any]:
    """Planifie un post à scheduled_at, ou le publie tout de suite si la date est omise."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            post = await posts_svc.get_post(session, ws, _id(post_id))
            post = await posts_svc.schedule_post(session, post, scheduled_at, actor="mcp")
        except DomainError as e:
            raise _fail(e) from None
    return _post(post, post.status == "draft")


@mcp.tool()
async def unschedule_post(ctx: Context, post_id: str) -> dict[str, Any]:
    """Annule la planification d'un post : il redevient un brouillon."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            post = await posts_svc.get_post(session, ws, _id(post_id))
            post = await posts_svc.unschedule_post(session, post)
        except DomainError as e:
            raise _fail(e) from None
    return _post(post)


@mcp.tool()
async def delete_post(ctx: Context, post_id: str) -> str:
    """Supprime un post de l'application (ne retire pas un post déjà publié du réseau)."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            post = await posts_svc.get_post(session, ws, _id(post_id))
            await posts_svc.delete_post(session, post)
        except DomainError as e:
            raise _fail(e) from None
    return "Post supprimé."


@mcp.tool()
async def list_posts(
    ctx: Context,
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Liste les posts. status : draft, scheduled, publishing, published, partial, failed.

    start et end filtrent sur la date de planification.
    """
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        posts = await posts_svc.list_posts(
            session, ws, status=status, start=start, end=end, limit=limit
        )
    return [_post(p) for p in posts]


@mcp.tool()
async def get_post(ctx: Context, post_id: str) -> dict[str, Any]:
    """Détail d'un post : statut par compte, lien public, message d'erreur éventuel."""
    ws = await _workspace(ctx)
    async with SessionLocal() as session:
        try:
            post = await posts_svc.get_post(session, ws, _id(post_id))
        except DomainError as e:
            raise _fail(e) from None
    return _post(post)


class ApiKeyGate:
    """Reject requests without a valid API key before they reach the MCP transport."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            token = _bearer(headers)
            async with SessionLocal() as session:
                ok = token and await workspace_for_api_key(session, token)
            if not ok:
                response = JSONResponse(
                    {"error": "Clé API invalide ou manquante."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                return await response(scope, receive, send)
        await self.app(scope, receive, send)


def build_mcp_app() -> ASGIApp:
    # Host/Origin checks guard unauthenticated local servers against DNS rebinding.
    # This one is remote and every request needs a bearer key a browser cannot supply.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return ApiKeyGate(
        mcp.streamable_http_app(
            streamable_http_path="/", stateless_http=True, transport_security=security
        )
    )
