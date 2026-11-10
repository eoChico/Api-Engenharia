from app.models.order_item import OrderItemStatus as S
from app.models.user import UserRole
from app.services.errors import ConflictError, ForbiddenError

NOT_OWNER = 'Esta mesa pertence a outro garçom'

_KITCHEN_STEPS = {(S.PENDING, S.PREPARING), (S.PREPARING, S.READY)}


def authorize_transition(old: S, new: S, role: UserRole, is_owner: bool) -> None:
    """Levanta ConflictError/ForbiddenError se a mudança de status não é permitida."""
    if old == new:
        raise ConflictError('O item já está nesse status')

    if new == S.CANCELED:
        if role == UserRole.MANAGER:
            return
        if role == UserRole.WAITER and is_owner:
            if old == S.PENDING:
                return
            raise ForbiddenError('Depois do preparo, só o gerente pode cancelar')
        raise ForbiddenError(NOT_OWNER if role == UserRole.WAITER else 'Sem permissão para cancelar')

    if (old, new) in _KITCHEN_STEPS:
        if role in (UserRole.KITCHEN, UserRole.MANAGER):
            return
        raise ForbiddenError('Só a cozinha altera o preparo')

    if (old, new) == (S.READY, S.DELIVERED):
        if role == UserRole.MANAGER or (role == UserRole.WAITER and is_owner):
            return
        raise ForbiddenError(NOT_OWNER if role == UserRole.WAITER else 'Sem permissão para entregar')

    raise ConflictError('Mudança de status inválida')
