from fastapi import APIRouter, HTTPException

from ..auth import LoginRequest, LoginResponse, mint_token
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    if body.passcode != settings().app_passcode:
        raise HTTPException(status_code=401, detail="wrong passcode")
    return mint_token()
