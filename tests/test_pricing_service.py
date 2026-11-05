"""Tests unitarios de PricingService.

Se reemplazan los repositorios y la publicación de eventos por mocks,
por lo que no se necesita MongoDB ni RabbitMQ.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.mov_pricing import MovType
from app.models.pricing import PricingCreate
from app.services import pricing_service as module
from app.services.pricing_service import pricing_service


@pytest.fixture
def mocks(monkeypatch):
    pricing_repo = AsyncMock()
    mov_repo = AsyncMock()
    publish = AsyncMock()
    monkeypatch.setattr(module, "pricing_repository", pricing_repo)
    monkeypatch.setattr(module, "mov_pricing_repository", mov_repo)
    monkeypatch.setattr(module, "publish_event", publish)
    return pricing_repo, mov_repo, publish


# ---------- get_price ----------

async def test_get_price_devuelve_precio_y_emite_evento(mocks):
    pricing_repo, _, publish = mocks
    pricing_repo.get_by_article_id.return_value = {"_id": 123, "articleId": "art-1", "price": 100.0}

    result = await pricing_service.get_price("art-1")

    assert result["price"] == 100.0
    assert result["_id"] == "123"
    publish.assert_awaited_once()
    assert publish.await_args.args[0] == "pricing.queried"


async def test_get_price_inexistente_devuelve_404(mocks):
    pricing_repo, _, publish = mocks
    pricing_repo.get_by_article_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await pricing_service.get_price("no-existe")

    assert exc.value.status_code == 404
    publish.assert_not_awaited()


# ---------- create_or_update_price ----------

async def test_set_sobre_articulo_nuevo_crea_precio(mocks):
    pricing_repo, mov_repo, publish = mocks
    pricing_repo.get_by_article_id.return_value = None
    pricing_repo.create.return_value = {"_id": "p1", "articleId": "art-1", "price": 50.0}

    result = await pricing_service.create_or_update_price(
        PricingCreate(articleId="art-1", price=50.0), MovType.SET, user_login="admin"
    )

    assert result["price"] == 50.0
    pricing_repo.create.assert_awaited_once()
    mov_repo.create.assert_awaited_once()
    assert publish.await_args.args[0] == "pricing.updated"
    assert publish.await_args.args[1]["price"] == 50.0


@pytest.mark.parametrize(
    "mov_type, actual, valor, esperado",
    [
        (MovType.SET, 100.0, 30.0, 30.0),
        (MovType.INCR, 100.0, 30.0, 130.0),
        (MovType.DECR, 100.0, 30.0, 70.0),
        (MovType.DECR, 100.0, 100.0, 0.0),
    ],
)
async def test_movimientos_sobre_articulo_existente(mocks, mov_type, actual, valor, esperado):
    pricing_repo, mov_repo, _ = mocks
    pricing_repo.get_by_article_id.return_value = {"_id": "p1", "articleId": "art-1", "price": actual}
    pricing_repo.update_price.return_value = {"_id": "p1", "articleId": "art-1", "price": esperado}

    await pricing_service.create_or_update_price(
        PricingCreate(articleId="art-1", price=valor), mov_type, user_login="admin"
    )

    pricing_repo.update_price.assert_awaited_once_with("art-1", esperado)
    # La auditoría guarda el valor del movimiento, no el precio resultante
    auditoria = mov_repo.create.await_args.args[0]
    assert auditoria.movType == mov_type
    assert auditoria.value == valor
    assert auditoria.userLogin == "admin"


async def test_decr_que_deja_precio_negativo_falla(mocks):
    pricing_repo, mov_repo, publish = mocks
    pricing_repo.get_by_article_id.return_value = {"_id": "p1", "articleId": "art-1", "price": 10.0}

    with pytest.raises(ValueError):
        await pricing_service.create_or_update_price(
            PricingCreate(articleId="art-1", price=20.0), MovType.DECR, user_login="admin"
        )

    pricing_repo.update_price.assert_not_awaited()
    mov_repo.create.assert_not_awaited()
    publish.assert_not_awaited()


async def test_decr_sobre_articulo_sin_precio_falla(mocks):
    pricing_repo, _, _ = mocks
    pricing_repo.get_by_article_id.return_value = None

    with pytest.raises(ValueError):
        await pricing_service.create_or_update_price(
            PricingCreate(articleId="art-1", price=5.0), MovType.DECR, user_login="admin"
        )

    pricing_repo.create.assert_not_awaited()


async def test_precio_negativo_falla(mocks):
    with pytest.raises(ValueError):
        await pricing_service.create_or_update_price(
            PricingCreate(articleId="art-1", price=-1.0), MovType.SET, user_login="admin"
        )


async def test_sin_usuario_falla(mocks):
    with pytest.raises(ValueError):
        await pricing_service.create_or_update_price(
            PricingCreate(articleId="art-1", price=10.0), MovType.SET, user_login=None
        )
