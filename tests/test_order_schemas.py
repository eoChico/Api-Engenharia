import pytest
from pydantic import ValidationError

from app.schemas.order import AddItemRequest, OpenTableRequest

PRODUCT = '3f2a1c9e-7d4b-4a5e-9c1d-2b8f6e0a1234'


def test_open_table_defaults_to_one_check():
    data = OpenTableRequest.model_validate({'party_size': 4})
    assert data.checks_count == 1


@pytest.mark.parametrize('payload', [
    {'party_size': 0},
    {'party_size': 100},
    {'party_size': 2, 'checks_count': 11},
    {'party_size': 2, 'waiter_id': PRODUCT},  # campo extra
])
def test_open_table_rejects_invalid_payloads(payload):
    with pytest.raises(ValidationError):
        OpenTableRequest.model_validate(payload)


def test_item_quantity_defaults_to_one_and_blank_notes_become_none():
    item = AddItemRequest.model_validate({'product_id': PRODUCT, 'notes': '   '})
    assert item.quantity == 1
    assert item.notes is None


@pytest.mark.parametrize('payload', [
    {'product_id': PRODUCT, 'quantity': 0},
    {'product_id': PRODUCT, 'quantity': 100},
    {'product_id': PRODUCT, 'unit_price_cents': 1},  # o preço nunca vem do cliente
    {'product_id': 'nao-e-uuid'},
])
def test_item_rejects_invalid_payloads(payload):
    with pytest.raises(ValidationError):
        AddItemRequest.model_validate(payload)
