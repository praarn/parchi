"""Authentication: signup, login, refresh (rotating), logout, me."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import cursor, query_one
from app.deps import CurrentUser, get_current_user
from app.models import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from app.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_pair(user_id: str, email: str) -> TokenPair:
    refresh = generate_refresh_token()
    with cursor() as cur:
        cur.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, hash_refresh_token(refresh), refresh_expiry()),
        )
    return TokenPair(access_token=create_access_token(user_id, email), refresh_token=refresh)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest) -> AuthResponse:
    if query_one("SELECT id FROM users WHERE email = %s", (body.email,)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )
    row = query_one(
        """
        INSERT INTO users (email, password_hash, name, preferred_language)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, name, preferred_language
        """,
        (body.email, hash_password(body.password), body.name, body.preferred_language),
    )
    pair = _issue_pair(str(row["id"]), row["email"])
    return AuthResponse(user=UserOut(**{**row, "id": str(row["id"])}), **pair.model_dump())


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    row = query_one("SELECT * FROM users WHERE email = %s", (body.email,))
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    pair = _issue_pair(str(row["id"]), row["email"])
    return AuthResponse(
        user=UserOut(
            id=str(row["id"]),
            email=row["email"],
            name=row["name"],
            preferred_language=row["preferred_language"],
        ),
        **pair.model_dump(),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest) -> TokenPair:
    token_hash = hash_refresh_token(body.refresh_token)
    row = query_one("SELECT * FROM refresh_tokens WHERE token_hash = %s", (token_hash,))
    now = datetime.now(UTC)
    if not row or row["revoked_at"] is not None or row["expires_at"] <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = query_one("SELECT id, email FROM users WHERE id = %s", (row["user_id"],))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    # Rotate: burn the presented token, hand back a fresh pair.
    with cursor() as cur:
        cur.execute("UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s", (row["id"],))
    return _issue_pair(str(user["id"]), user["email"])


@router.post("/logout")
def logout(body: LogoutRequest) -> dict:
    with cursor() as cur:
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
            (hash_refresh_token(body.refresh_token),),
        )
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)) -> UserOut:
    row = query_one(
        "SELECT id, email, name, preferred_language FROM users WHERE id = %s",
        (user.id,),
    )
    return UserOut(**{**row, "id": str(row["id"])})
