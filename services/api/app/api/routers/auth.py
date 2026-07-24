from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.api.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.application.auth import AuthService
from app.infrastructure.security.sessions import refresh_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, service: AuthService = Depends(get_auth_service)) -> UserOut:
    user = service.register(payload.email, payload.password)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, service: AuthService = Depends(get_auth_service)) -> TokenOut:
    tokens = service.login(payload.email, payload.password)
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn) -> TokenOut:
    tokens = refresh_session(payload.refresh_token)
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)
