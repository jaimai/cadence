from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.config import get_settings
from app.deps import CurrentAuth, Session
from app.models import Membership, User, Workspace
from app.schemas import Credentials, WorkspaceOut
from app.security import (
    SESSION_COOKIE,
    SESSION_DAYS,
    create_session_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        domain=s.cookie_domain or None,
    )


@router.post("/signup")
async def signup(body: Credentials, response: Response, session: Session) -> dict:
    if not get_settings().allow_signup:
        raise HTTPException(403, "Les inscriptions sont fermées.")
    email = body.email.lower()
    if (await session.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail.")
    user = User(email=email, password_hash=hash_password(body.password))
    workspace = Workspace(name="Mon espace")
    session.add_all([user, workspace])
    await session.flush()
    session.add(Membership(user_id=user.id, workspace_id=workspace.id))
    await session.commit()
    _set_cookie(response, create_session_token(user.id, workspace.id))
    return {"email": user.email}


@router.post("/login")
async def login(body: Credentials, response: Response, session: Session) -> dict:
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "E-mail ou mot de passe incorrect.")
    member = (
        await session.execute(select(Membership).where(Membership.user_id == user.id).limit(1))
    ).scalar_one()
    _set_cookie(response, create_session_token(user.id, member.workspace_id))
    return {"email": user.email}


@router.post("/logout")
async def logout(response: Response) -> dict:
    s = get_settings()
    response.delete_cookie(
        SESSION_COOKIE,
        domain=s.cookie_domain or None,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
    )
    return {"ok": True}


@router.get("/me")
async def me(auth: CurrentAuth, session: Session) -> dict:
    user = await session.get(User, auth.user_id)
    workspace = await session.get(Workspace, auth.workspace_id)
    return {"email": user.email, "workspace": WorkspaceOut.model_validate(workspace)}
