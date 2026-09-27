"""Konten, Anmeldung und Verknüpfung von Riot-Accounts über das Uploader-Tool."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from . import auth
from .deps import SESSION_COOKIE, CurrentUser, RateLimit, Service, client_ip, get_user
from .schemas import (ImportIn, ImportOut, KnownIn, KnownOut, LinkCodeOut, LoginIn, MeOut, PasswordIn,
                      RegisterIn, RiotLinkOut, UploaderLinkIn, UploaderLinkOut, UploaderStatusIn,
                      UploaderStatusOut, UserOut)
from .services import PrimeStats
from .store import UserAccount

router = APIRouter(prefix="/api")

LINK_CODE_LIFETIME = timedelta(minutes=15)
login_limit = RateLimit(limit=10, window=300)
register_limit = RateLimit(limit=5, window=3600)
link_limit = RateLimit(limit=10, window=300)


def _set_session(request: Request, response: Response, service: PrimeStats, user: UserAccount) -> None:
    settings = request.app.state.settings
    token = auth.new_token()
    lifetime = timedelta(days=settings.session_days)
    service.store.create_session(user.id, token, lifetime)
    secure = request.url.scheme == "https" if settings.cookie_secure == "auto" else settings.cookie_secure == "1"
    response.set_cookie(SESSION_COOKIE, token, max_age=int(lifetime.total_seconds()), httponly=True,
                        samesite="lax", secure=secure, path="/")


def _me(service: PrimeStats, user: UserAccount | None) -> MeOut:
    if user is None:
        return MeOut(user=None)
    links = service.store.linked_riot_accounts(user.id)
    return MeOut(user=UserOut.model_validate(user), riot_accounts=[RiotLinkOut.model_validate(r) for r in links])


# ---------------------------------------------------------------- Anmeldung
@router.post("/auth/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, response: Response, service: Service):
    register_limit.check(client_ip(request))
    user = service.store.create_user(body.username, auth.hash_password(body.password))
    if user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieser Benutzername ist bereits vergeben.")
    _set_session(request, response, service, user)
    return _me(service, user)


@router.post("/auth/login", response_model=MeOut)
def login(body: LoginIn, request: Request, response: Response, service: Service):
    key = f"{client_ip(request)}:{body.username.lower()}"
    login_limit.check(key)
    found = service.store.user_credentials(body.username)
    if not found or not auth.verify_password(body.password, found[1]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzername oder Passwort falsch.")
    login_limit.reset(key)
    _set_session(request, response, service, found[0])
    return _me(service, found[0])


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, service: Service):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.store.delete_session(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/auth/me", response_model=MeOut)
def me(service: Service, user: Annotated[UserAccount | None, Depends(get_user)]):
    return _me(service, user)


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordIn, service: Service, user: CurrentUser):
    _, stored = service.store.user_credentials(user.username)
    if not auth.verify_password(body.old_password, stored):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das alte Passwort stimmt nicht.")
    service.store.set_password(user.id, auth.hash_password(body.new_password))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------- Riot-Verknüpfungen
@router.post("/me/link-code", response_model=LinkCodeOut)
def create_link_code(service: Service, user: CurrentUser):
    """Einmal-Code, den man im Uploader-Tool eingibt, um den dort eingeloggten Riot-Account zu verknüpfen."""
    code = auth.new_link_code()
    expires = service.store.create_link_code(user.id, code, LINK_CODE_LIFETIME)
    return LinkCodeOut(code=code, expires_at=expires)


@router.delete("/me/riot/{puuid}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(puuid: str, service: Service, user: CurrentUser):
    if not service.store.unlink_riot(user.id, puuid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verknüpfung nicht gefunden.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------- Uploader-Tool
@router.post("/uploader/status", response_model=UploaderStatusOut)
def uploader_status(body: UploaderStatusIn, service: Service):
    """Ist der im Client eingeloggte Riot-Account (mit diesem Geräteschlüssel) verknüpft?"""
    user_id = service.store.riot_link_owner(body.puuid, body.key or "") if body.key else None
    user = service.store.get_user(user_id) if user_id else None
    return UploaderStatusOut(linked=user is not None, username=user.username if user else None)


@router.post("/uploader/link", response_model=UploaderLinkOut)
def uploader_link(body: UploaderLinkIn, request: Request, service: Service):
    """Löst einen Verknüpfungscode ein. Wer den Client mit diesem Riot-Account geöffnet hat,
    verknüpft ihn mit dem Konto, zu dem der Code gehört (eine bestehende Verknüpfung wird ersetzt)."""
    link_limit.check(client_ip(request))
    user_id = service.store.redeem_link_code(auth.normalize_code(body.code))
    user = service.store.get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code ungültig oder abgelaufen – bitte auf der Website neu erzeugen.")
    key = auth.new_token()
    service.store.link_riot(user.id, body.puuid, body.game_name, body.tag_line, key)
    service.store.put_account(f"{body.game_name}#{body.tag_line}",
                              {"puuid": body.puuid, "gameName": body.game_name, "tagLine": body.tag_line})
    return UploaderLinkOut(username=user.username, key=key)


def uploader_account(service: Service, x_riot_puuid: Annotated[str, Header()] = "",
                     x_link_key: Annotated[str, Header()] = "") -> tuple[UserAccount, set[str], str]:
    """Authentifiziert das Tool über den eingeloggten Riot-Account und dessen Geräteschlüssel."""
    user_id = service.store.riot_link_owner(x_riot_puuid, x_link_key) if x_riot_puuid and x_link_key else None
    user = service.store.get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Dieser Riot-Account ist nicht (mehr) mit einem PrimeStats-Konto verknüpft.")
    puuids = {link.puuid for link in service.store.linked_riot_accounts(user.id)}
    return user, puuids, x_riot_puuid


UploaderAccount = Annotated[tuple[UserAccount, set[str], str], Depends(uploader_account)]


@router.post("/uploader/known", response_model=KnownOut)
def uploader_known(body: KnownIn, service: Service, _: UploaderAccount):
    """Welche der Match-IDs sind bereits gespeichert? (Das Tool lädt nur den Rest hoch.)"""
    return KnownOut(known=sorted(service.known_matches(body.match_ids)))


@router.post("/uploader/games", response_model=ImportOut)
def uploader_games(body: ImportIn, service: Service, account: UploaderAccount):
    user, puuids, puuid = account
    result = service.import_lcu([item.model_dump() for item in body.games], uploader=user.username,
                                allowed_puuids=puuids)
    service.store.touch_riot_link(puuid)
    return ImportOut(**result.__dict__)
