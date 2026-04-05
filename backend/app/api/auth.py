from __future__ import annotations

from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.db.session import get_db
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser
from backend.app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserResponse

router = APIRouter()


def _tiendanube_status_for_store(db: Session, store_id: int) -> Tuple[Optional[str], bool]:
    """Retorna (external_store_id, needs_tiendanube) alineado con /api/onboarding/status."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        return None, True
    inst = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store.id,
            StoreInstallation.order_source_type == "tiendanube",
        )
        .first()
    )
    has_token = bool(inst and inst.is_active and (inst.access_token or "").strip())
    return store.external_store_id, not has_token


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(StoreUser).filter(StoreUser.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, store_id=user.store_id)
    return LoginResponse(access_token=token)


@router.post("/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = str(body.email).lower().strip()
    if db.query(StoreUser).filter(StoreUser.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")

    store = Store(
        name=body.store_name.strip(),
        external_store_id=None,
        country="",
        status="active",
    )
    db.add(store)
    db.flush()

    settings = StoreSettings(
        store_id=store.id,
        ecommerce_sync_enabled=True,
        whatsapp_enabled=False,
        onboarding_status="pending",
    )
    db.add(settings)

    user = StoreUser(
        store_id=store.id,
        email=email,
        password_hash=hash_password(body.password),
        role="owner",
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")

    db.refresh(user)
    token = create_access_token(user_id=user.id, store_id=user.store_id)
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: StoreUser = Depends(get_current_user), db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == current_user.store_id).first()
    tn_id, needs_tn = _tiendanube_status_for_store(db, current_user.store_id)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        store_id=current_user.store_id,
        role=current_user.role,
        store_name=store.name if store else None,
        tiendanube_user_id=tn_id,
        needs_tiendanube=needs_tn,
    )
