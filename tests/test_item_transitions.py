import pytest

from app.models.order_item import OrderItemStatus as S
from app.models.user import UserRole as R
from app.services.errors import ConflictError, ForbiddenError
from app.services.item_rules import authorize_transition


def test_kitchen_runs_the_preparation_steps():
    authorize_transition(S.PENDING, S.PREPARING, R.KITCHEN, False)
    authorize_transition(S.PREPARING, S.READY, R.KITCHEN, False)


def test_waiter_cannot_run_kitchen_steps():
    with pytest.raises(ForbiddenError):
        authorize_transition(S.PENDING, S.PREPARING, R.WAITER, True)


def test_kitchen_cannot_deliver():
    with pytest.raises(ForbiddenError):
        authorize_transition(S.READY, S.DELIVERED, R.KITCHEN, False)


def test_only_the_owner_waiter_delivers():
    authorize_transition(S.READY, S.DELIVERED, R.WAITER, True)
    with pytest.raises(ForbiddenError):
        authorize_transition(S.READY, S.DELIVERED, R.WAITER, False)


def test_waiter_cancels_only_pending_items():
    authorize_transition(S.PENDING, S.CANCELED, R.WAITER, True)
    with pytest.raises(ForbiddenError):
        authorize_transition(S.PREPARING, S.CANCELED, R.WAITER, True)


def test_waiter_cannot_cancel_on_someone_elses_table():
    with pytest.raises(ForbiddenError):
        authorize_transition(S.PENDING, S.CANCELED, R.WAITER, False)


def test_manager_cancels_any_active_item():
    for old in (S.PENDING, S.PREPARING, S.READY, S.DELIVERED):
        authorize_transition(old, S.CANCELED, R.MANAGER, False)


def test_cashier_cannot_change_items():
    with pytest.raises(ForbiddenError):
        authorize_transition(S.PENDING, S.CANCELED, R.CASHIER, False)
    with pytest.raises(ForbiddenError):
        authorize_transition(S.READY, S.DELIVERED, R.CASHIER, False)


def test_invalid_jumps_are_rejected():
    with pytest.raises(ConflictError):
        authorize_transition(S.PENDING, S.DELIVERED, R.MANAGER, False)
    with pytest.raises(ConflictError):
        authorize_transition(S.CANCELED, S.PENDING, R.MANAGER, False)


def test_same_status_is_rejected():
    with pytest.raises(ConflictError):
        authorize_transition(S.READY, S.READY, R.KITCHEN, False)
