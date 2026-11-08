import pytest
from pydantic import ValidationError

from app.models.product import ProductCategory
from app.schemas.product import ProductCreate, ProductUpdate


def test_valid_payload_is_accepted():
    # JSON como chega da API: a categoria vem como texto e vira enum.
    product = ProductCreate.model_validate(
        {'name': 'Água', 'category': 'drink', 'price_cents': 500}
    )
    assert product.category is ProductCategory.DRINK
    assert product.needs_kitchen is None  # o service decide o padrão


def test_negative_price_is_rejected():
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({'name': 'Água', 'category': 'drink', 'price_cents': -1})


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(
            {'name': 'Água', 'category': 'drink', 'price_cents': 500, 'is_active': False}
        )


def test_invalid_category_is_rejected():
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({'name': 'Água', 'category': 'bebida', 'price_cents': 500})


def test_update_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({})


def test_update_rejects_null_values():
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({'price_cents': None})
