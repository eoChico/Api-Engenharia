import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def record(
    db: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    ip: str | None = None,
    detail: dict | None = None,
) -> None:
    """Só adiciona à sessão: entra na mesma transação de quem chamou."""
    db.add(AuditLog(action=action, actor_id=actor_id, target_id=target_id, ip=ip, detail=detail))
