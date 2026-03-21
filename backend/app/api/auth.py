from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.core.security import verify_password, create_access_token
from backend.app.db.session import get_db
from backend.app.models.user import StoreUser
from backend.app.schemas.auth import LoginRequest, LoginResponse, UserResponse

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(StoreUser).filter(StoreUser.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, store_id=user.store_id)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: StoreUser = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.app.models.store import Store

    store = db.query(Store).filter(Store.id == current_user.store_id).first()
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        store_id=current_user.store_id,
        role=current_user.role,
        store_name=store.name if store else None,
    )
