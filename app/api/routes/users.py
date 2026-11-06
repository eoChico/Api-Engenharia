import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, ManagerUser, Meta
from app.schemas.user import UserCreate, UserRead, UserUpdateAdmin
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, actor: ManagerUser, db: DbSession, meta: Meta):
    try:
        return await user_service.create_user(db, data, actor, meta.ip)
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado") from None


@router.get("", response_model=list[UserRead])
async def list_users(
    actor: ManagerUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await user_service.list_users(db, limit, offset)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, actor: ManagerUser, db: DbSession):
    user = await user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, data: UserUpdateAdmin, actor: ManagerUser, db: DbSession, meta: Meta
):
    target = await user_service.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    try:
        return await user_service.update_user(db, target, data, actor, meta.ip)
    except user_service.CannotModifySelfError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Você não pode alterar seu próprio papel ou status"
        ) from None
    except user_service.LastManagerError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Não é possível ficar sem nenhum gerente ativo"
        ) from None
