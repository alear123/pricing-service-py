"""Tests de la capa HTTP (controllers).

Se reemplaza la autenticación contra AuthGo con dependency_overrides de
FastAPI y los services con mocks. El TestClient se usa sin context manager,
así no se ejecuta el lifespan (no se conecta a MongoDB ni RabbitMQ).
"""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.controllers import coupon_controller, pricing_controller
from app.security import get_current_user
from main import app

ADMIN = {"login": "admin", "permissions": ["admin"]}
USER = {"login": "juan", "permissions": ["user"]}
AUTH = {"Authorization": "Bearer token"}


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def login_as(user):
    app.dependency_overrides[get_current_user] = lambda: user


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_price(client, monkeypatch):
    login_as(USER)
    service = AsyncMock()
    service.get_price.return_value = {"articleId": "art-1", "price": 100.0}
    monkeypatch.setattr(pricing_controller, "pricing_service", service)

    response = client.get("/pricing/art-1", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["price"] == 100.0


def test_actualizar_precio_requiere_admin(client, monkeypatch):
    login_as(USER)
    service = AsyncMock()
    monkeypatch.setattr(pricing_controller, "pricing_service", service)

    response = client.post("/pricing", json={"articleId": "art-1", "price": 10}, headers=AUTH)

    assert response.status_code == 403
    service.create_or_update_price.assert_not_awaited()


def test_actualizar_precio_como_admin(client, monkeypatch):
    login_as(ADMIN)
    service = AsyncMock()
    service.create_or_update_price.return_value = {"articleId": "art-1", "price": 110.0}
    monkeypatch.setattr(pricing_controller, "pricing_service", service)

    response = client.post(
        "/pricing?movType=INCR", json={"articleId": "art-1", "price": 10}, headers=AUTH
    )

    assert response.status_code == 200
    assert service.create_or_update_price.await_args.kwargs["mov_type"].value == "INCR"
    assert service.create_or_update_price.await_args.kwargs["user_login"] == "admin"


def test_error_de_negocio_se_traduce_a_400(client, monkeypatch):
    login_as(ADMIN)
    service = AsyncMock()
    service.create_or_update_price.side_effect = ValueError("precio inválido")
    monkeypatch.setattr(pricing_controller, "pricing_service", service)

    response = client.post("/pricing", json={"articleId": "art-1", "price": 10}, headers=AUTH)

    assert response.status_code == 400
    assert response.json()["detail"] == "precio inválido"


def test_crear_cupon_requiere_admin(client, monkeypatch):
    login_as(USER)
    service = AsyncMock()
    monkeypatch.setattr(coupon_controller, "coupon_service", service)

    response = client.post(
        "/coupons",
        json={
            "couponCode": "PROMO",
            "usageLimit": 10,
            "discountType": "PERCENTAGE",
            "discountValue": 20,
            "startDate": "2026-01-01T00:00:00",
            "expirationDate": "2026-12-31T00:00:00",
        },
        headers=AUTH,
    )

    assert response.status_code == 403
    service.create_coupon.assert_not_awaited()


def test_aplicar_cupon_pasa_usuario_y_token(client, monkeypatch):
    login_as(USER)
    service = AsyncMock()
    service.apply_coupon.return_value = {"status": "valid"}
    monkeypatch.setattr(coupon_controller, "coupon_service", service)

    response = client.post("/coupons/apply", json={"couponCode": "PROMO"}, headers=AUTH)

    assert response.status_code == 200
    kwargs = service.apply_coupon.await_args.kwargs
    assert kwargs["user_login"] == "juan"
    assert kwargs["token"] == "token"
