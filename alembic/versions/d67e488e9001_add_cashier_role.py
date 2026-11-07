"""add cashier role

Revision ID: d67e488e9001
Revises: fedf4559c497
Create Date: 2026-11-06 21:08:19.439676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd67e488e9001'
down_revision: Union[str, Sequence[str], None] = 'fedf4559c497'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ROLES = "'waiter', 'manager', 'kitchen'"
NEW_ROLES = "'waiter', 'manager', 'kitchen', 'cashier'"



from alembic import op

# (mantenha os revision/down_revision que o Alembic gerou)

OLD_ROLES = "'waiter', 'manager', 'kitchen'"
NEW_ROLES = "'waiter', 'manager', 'kitchen', 'cashier'"


def upgrade() -> None:
    op.drop_constraint(op.f('ck_users_user_role'), 'users', type_='check')
    op.create_check_constraint(
        op.f('ck_users_user_role'), 'users', f'role IN ({NEW_ROLES})'
    )


def downgrade() -> None:
    # Falha se ainda existir usuário caixa: migre ou remova esses usuários antes.
    op.drop_constraint(op.f('ck_users_user_role'), 'users', type_='check')
    op.create_check_constraint(
        op.f('ck_users_user_role'), 'users', f'role IN ({OLD_ROLES})'
    )
