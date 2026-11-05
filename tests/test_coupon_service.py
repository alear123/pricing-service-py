"""Tests unitarios de CouponService.

Se reemplazan los repositorios, el cliente de CartGo y la publicación de
eventos por mocks, por lo que no se necesita ningún servicio externo.
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.coupon import CouponCreate, DiscountType
from app.models.coupon_usage import CouponUsageCreate
from app.services import coupon_service as module
from app.services.coupon_service import coupon_service


@pytest.fixture
def mocks(monkeypatch):
    coupon_repo = AsyncMock()
    pricing_repo = AsyncMock()
    validate_cart = AsyncMock()
    publish = AsyncMock()
    monkeypatch.setattr(module, "coupon_repository", coupon_repo)
    monkeypatch.setattr(module, "pricing_repository", pricing_repo)
    monkeypatch.setattr(module, "validate_cart_exists", validate_cart)
    monkeypatch.setattr(module, "publish_event", publish)

    # Escenario base válido: carrito con 2 x art-1 ($100) + 1 x art-2 ($50) = $250
    validate_cart.return_value = {
        "_id": "cart-1",
        "articles": [
            {"articleId": "art-1", "quantity": 2},
            {"articleId": "art-2", "quantity": 1},
        ],
    }
    precios = {"art-1": {"price": 100.0}, "art-2": {"price": 50.0}}
    pricing_repo.get_by_article_id.side_effect = lambda article_id: precios.get(article_id)
    coupon_repo.get_by_code.return_value = make_coupon()
    coupon_repo.count_usages.return_value = 0
    coupon_repo.is_applied_to_cart.return_value = False

    return coupon_repo, pricing_repo, validate_cart, publish


def make_coupon(**overrides):
    now = datetime.utcnow()
    coupon = {
        "_id": "c1",
        "couponCode": "PROMO",
        "usageLimit": 10,
        "discountType": "PERCENTAGE",
        "discountValue": 20.0,
        "startDate": now - timedelta(days=1),
        "expirationDate": now + timedelta(days=1),
    }
    coupon.update(overrides)
    return coupon


def coupon_create(**overrides):
    now = datetime.utcnow()
    data = dict(
        couponCode="PROMO",
        usageLimit=10,
        discountType=DiscountType.PERCENTAGE,
        discountValue=20.0,
        startDate=now,
        expirationDate=now + timedelta(days=30),
    )
    data.update(overrides)
    return CouponCreate(**data)


async def apply(code="PROMO"):
    return await coupon_service.apply_coupon(
        CouponUsageCreate(couponCode=code), user_login="juan", token="token"
    )


# ---------- create_coupon ----------

async def test_create_coupon_guarda_y_emite_evento(mocks):
    coupon_repo, _, _, publish = mocks
    coupon_repo.get_by_code.return_value = None
    coupon_repo.create.return_value = make_coupon()

    await coupon_service.create_coupon(coupon_create())

    coupon_repo.create.assert_awaited_once()
    assert publish.await_args.args[0] == "coupon.created"


async def test_create_coupon_duplicado_falla(mocks):
    coupon_repo, _, _, _ = mocks  # get_by_code ya devuelve un cupón existente

    with pytest.raises(HTTPException) as exc:
        await coupon_service.create_coupon(coupon_create())

    assert exc.value.status_code == 400
    coupon_repo.create.assert_not_awaited()


async def test_create_coupon_con_fechas_invertidas_falla(mocks):
    now = datetime.utcnow()
    with pytest.raises(ValueError):
        await coupon_service.create_coupon(
            coupon_create(startDate=now, expirationDate=now - timedelta(days=1))
        )


async def test_create_coupon_con_descuento_negativo_falla(mocks):
    with pytest.raises(ValueError):
        await coupon_service.create_coupon(coupon_create(discountValue=-5))


# ---------- apply_coupon: cálculo del descuento ----------

async def test_apply_descuento_porcentual(mocks):
    coupon_repo, _, _, _ = mocks

    result = await apply()

    assert result["subtotal"] == 250.0
    assert result["discountAmount"] == 50.0  # 20% de 250
    assert result["totalWithDiscount"] == 200.0
    coupon_repo.save_pending_coupon.assert_awaited_once_with(
        cart_id="cart-1", coupon_code="PROMO", user_login="juan"
    )


async def test_apply_descuento_fijo(mocks):
    coupon_repo, _, _, _ = mocks
    coupon_repo.get_by_code.return_value = make_coupon(discountType="FIXED", discountValue=30.0)

    result = await apply()

    assert result["discountAmount"] == 30.0
    assert result["totalWithDiscount"] == 220.0


async def test_apply_descuento_fijo_no_supera_el_subtotal(mocks):
    coupon_repo, _, _, _ = mocks
    coupon_repo.get_by_code.return_value = make_coupon(discountType="FIXED", discountValue=1000.0)

    result = await apply()

    assert result["discountAmount"] == 250.0
    assert result["totalWithDiscount"] == 0.0


async def test_apply_ignora_articulos_sin_precio(mocks):
    _, _, validate_cart, _ = mocks
    validate_cart.return_value["articles"].append({"articleId": "sin-precio", "quantity": 3})

    result = await apply()

    assert result["subtotal"] == 250.0


# ---------- apply_coupon: validaciones ----------

@pytest.mark.parametrize(
    "coupon_overrides, count_usages, already_applied",
    [
        pytest.param({"expirationDate": datetime.utcnow() - timedelta(days=1)}, 0, False, id="expirado"),
        pytest.param({"startDate": datetime.utcnow() + timedelta(days=1)}, 0, False, id="aun-no-vigente"),
        pytest.param({"usageLimit": 5}, 5, False, id="limite-de-usos-alcanzado"),
        pytest.param({}, 0, True, id="carrito-con-cupon-previo"),
    ],
)
async def test_apply_rechaza_cupon_invalido(mocks, coupon_overrides, count_usages, already_applied):
    coupon_repo, _, _, _ = mocks
    coupon_repo.get_by_code.return_value = make_coupon(**coupon_overrides)
    coupon_repo.count_usages.return_value = count_usages
    coupon_repo.is_applied_to_cart.return_value = already_applied

    with pytest.raises(HTTPException) as exc:
        await apply()

    assert exc.value.status_code == 400
    coupon_repo.save_pending_coupon.assert_not_awaited()


async def test_apply_cupon_inexistente_devuelve_404(mocks):
    coupon_repo, _, _, _ = mocks
    coupon_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc:
        await apply("NO-EXISTE")

    assert exc.value.status_code == 404


async def test_apply_sin_token_devuelve_401(mocks):
    with pytest.raises(HTTPException) as exc:
        await coupon_service.apply_coupon(CouponUsageCreate(couponCode="PROMO"), token="")

    assert exc.value.status_code == 401


# ---------- process_order_created_usage (evento order_placed) ----------

ORDER = {"orderId": "o1", "cartId": "cart-1", "userId": "u1"}


async def test_orden_con_cupon_reservado_registra_uso(mocks):
    coupon_repo, _, _, publish = mocks
    coupon_repo.get_and_delete_pending_coupon.return_value = {"coupon_code": "PROMO"}
    coupon_repo.register_usage.return_value = {"_id": "usage-1"}

    await coupon_service.process_order_created_usage(ORDER)

    coupon_repo.register_usage.assert_awaited_once()
    assert publish.await_args.kwargs["routing_key"] == "coupon.applied"
    assert publish.await_args.kwargs["message_data"]["status"] == "SUCCESS"


async def test_orden_sin_cupon_reservado(mocks):
    coupon_repo, _, _, publish = mocks
    coupon_repo.get_and_delete_pending_coupon.return_value = None

    await coupon_service.process_order_created_usage(ORDER)

    coupon_repo.register_usage.assert_not_awaited()
    assert publish.await_args.kwargs["routing_key"] == "coupon.processed"
    assert publish.await_args.kwargs["message_data"]["status"] == "NOT_APPLIED"


async def test_orden_con_cupon_que_alcanzo_el_limite(mocks):
    coupon_repo, _, _, publish = mocks
    coupon_repo.get_and_delete_pending_coupon.return_value = {"coupon_code": "PROMO"}
    coupon_repo.get_by_code.return_value = make_coupon(usageLimit=3)
    coupon_repo.count_usages.return_value = 3

    await coupon_service.process_order_created_usage(ORDER)

    coupon_repo.register_usage.assert_not_awaited()
    assert publish.await_args.kwargs["routing_key"] == "coupon.failed"
    assert publish.await_args.kwargs["message_data"]["status"] == "LIMIT_EXCEEDED"


async def test_orden_sin_cart_id_se_descarta(mocks):
    coupon_repo, _, _, publish = mocks

    await coupon_service.process_order_created_usage({"orderId": "o1"})

    coupon_repo.get_and_delete_pending_coupon.assert_not_awaited()
    publish.assert_not_awaited()
