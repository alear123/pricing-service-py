from datetime import datetime
from fastapi import HTTPException, status
from app.repositories.coupon_repository import coupon_repository
from app.models.coupon import CouponCreate, CouponUpdate
from app.models.coupon_usage import CouponUsageCreate
from app.models.events import CouponCreatedEvent
from app.rabbitmq import publish_event
from typing import Optional
from app.clients.cart_client import validate_cart_exists
from app.repositories.pricing_repository import pricing_repository

class CouponService:

    async def create_coupon(self, coupon_data: CouponCreate) -> dict:
        # 1. Validaciones de negocio en Service
        if not coupon_data or not coupon_data.couponCode:
            raise ValueError("Datos de cupón incompletos.")
        
        if coupon_data.discountValue is not None and coupon_data.discountValue < 0:
            raise ValueError("El valor del descuento no puede ser negativo.")

        if coupon_data.startDate and coupon_data.expirationDate:
            if coupon_data.startDate >= coupon_data.expirationDate:
                raise ValueError("La fecha de inicio debe ser anterior a la fecha de expiración.")

        code_clean = coupon_data.couponCode.strip()
        existing = await coupon_repository.get_by_code(code_clean)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El cupón con código '{code_clean}' ya existe."
            )

        coupon = await coupon_repository.create(coupon_data)

        # Evento RabbitMQ
        event = CouponCreatedEvent(
            timestamp=datetime.utcnow(),
            couponCode=coupon["couponCode"],
            discountType=coupon["discountType"],
            discountValue=coupon["discountValue"],
            startDate=coupon.get("startDate"),
            expirationDate=coupon.get("expirationDate")
        )
        await publish_event("coupon.created", event.model_dump(mode="json"))

        return coupon

    async def update_coupon(self, coupon_code: str, update_data: CouponUpdate) -> dict:
        if not coupon_code or not isinstance(coupon_code, str):
            raise ValueError("El código del cupón a actualizar es inválido.")

        if update_data.discountValue is not None and update_data.discountValue < 0:
            raise ValueError("El nuevo valor de descuento no puede ser negativo.")

        updated = await coupon_repository.update(coupon_code.strip(), update_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el cupón '{coupon_code}'."
            )
        return updated

    async def apply_coupon(
        self, 
        usage_data: CouponUsageCreate, 
        user_login: Optional[str] = None,
        token: Optional[str] = None
    ) -> dict:
        if not usage_data or not usage_data.couponCode:
            raise ValueError("Se requiere un código de cupón para proceder con la aplicación.")

        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se requiere un token de autenticación válido para aplicar el cupón."
            )
            
        # 1. Obtener el carrito activo
        cart = await validate_cart_exists(token)
        if not cart or "_id" not in cart:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo obtener un carrito válido asociado a la sesión actual."
            )
        
        cart_id = str(cart["_id"])
        coupon_code = usage_data.couponCode.strip()

        # 2. Buscar el cupón
        coupon = await coupon_repository.get_by_code(coupon_code)
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El cupón '{coupon_code}' no existe."
            )

        # 3. Validaciones de fecha de vigencia
        now = datetime.utcnow()
        if coupon.get("startDate") and now < coupon["startDate"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cupón aún no está vigente."
            )

        if coupon.get("expirationDate") and now > coupon["expirationDate"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cupón ha expirado."
            )

        # 4. Validar límite de uso global
        current_uses = await coupon_repository.count_usages(coupon["_id"])
        usage_limit = coupon.get("usageLimit")
        if usage_limit is not None and current_uses >= usage_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El cupón ha alcanzado su límite máximo de usos."
            )

        # 5. Validar si ya fue aplicado a este carrito
        already_applied = await coupon_repository.is_applied_to_cart(cart_id)
        if already_applied:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya se ha aplicado un cupón previamente a este carrito."
            )

        # --- CÁLCULO DE PRECIOS EN MEMORIA ---
        subtotal = 0.0
        articles = cart.get("articles", [])
        
        for item in articles:
            article_id = item.get("articleId")
            quantity = item.get("quantity", 1)
            
            if article_id:
                pricing = await pricing_repository.get_by_article_id(str(article_id))
                if pricing and "price" in pricing:
                    subtotal += float(pricing["price"]) * quantity

        discount_type = coupon.get("discountType")
        discount_value = float(coupon.get("discountValue", 0))

        if discount_type == "PERCENTAGE":
            discount_amount = round((subtotal * discount_value) / 100.0, 2)
        elif discount_type == "FIXED":
            discount_amount = min(discount_value, subtotal)
        else:
            discount_amount = 0.0

        total_with_discount = max(0.0, round(subtotal - discount_amount, 2))

        # 6. Guardar reserva temporal
        await coupon_repository.save_pending_coupon(
            cart_id=cart_id, 
            coupon_code=coupon["couponCode"], 
            user_login=user_login
        )

        return {
            "status": "valid",
            "couponCode": coupon["couponCode"],
            "cartId": cart_id,
            "discountType": discount_type,
            "discountValue": discount_value,
            "subtotal": round(subtotal, 2),
            "discountAmount": discount_amount,
            "totalWithDiscount": total_with_discount,
            "appliedBy": user_login
        }

    async def process_order_created_usage(self, order_data: dict) -> None:
        if not order_data or not isinstance(order_data, dict):
            print(" Evento descartado: El payload recibido de la orden no es un diccionario válido.")
            return

        order_id = str(order_data.get("orderId", ""))
        cart_id = str(order_data.get("cartId", ""))
        user_id = str(order_data.get("userId", ""))
        user_login = order_data.get("userLogin") or user_id

        if not cart_id:
            print(f" No se puede procesar uso de cupón para la orden '{order_id}': cartId ausente.")
            return

        # 1. Obtener y eliminar la reserva pendiente
        pending_entry = await coupon_repository.get_and_delete_pending_coupon(cart_id, user_id)

        if not pending_entry:
            print(f"ℹ La orden '{order_id}' se creó sin un cupón pendiente.")
            await publish_event(
                routing_key="coupon.processed",
                message_data={
                    "status": "NOT_APPLIED",
                    "orderId": order_id,
                    "cartId": cart_id,
                    "reason": "No había cupón pendiente reservado para este carrito.",
                    "discountAmount": 0.0
                }
            )
            return

        coupon_code = pending_entry.get("coupon_code")
        coupon = await coupon_repository.get_by_code(coupon_code) if coupon_code else None

        # 2. Validar existencia del cupón
        if not coupon:
            print(f" El cupón '{coupon_code}' no existe en la base de datos.")
            await publish_event(
                routing_key="coupon.processed",
                message_data={
                    "status": "FAILED",
                    "orderId": order_id,
                    "cartId": cart_id,
                    "couponCode": coupon_code,
                    "reason": "El cupón registrado ya no existe en el catálogo."
                }
            )
            return

        # 3. Consumir un uso de forma atómica (chequeo de límite + incremento en una sola operación)
        usage_limit = coupon.get("usageLimit")
        if not await coupon_repository.try_consume_usage(coupon["couponCode"]):
            print(f" El cupón '{coupon_code}' alcanzó el límite máximo de usos ({usage_limit}).")
            await publish_event(
                routing_key="coupon.failed",
                message_data={
                    "status": "LIMIT_EXCEEDED",
                    "orderId": order_id,
                    "cartId": cart_id,
                    "couponCode": coupon_code,
                    "reason": f"El cupón alcanzó su límite máximo de usos ({usage_limit})."
                }
            )
            return

        # 4. Registrar uso e informar éxito
        try:
            usage = await coupon_repository.register_usage(
                coupon_id=coupon["_id"],
                cart_id=cart_id,
                order_id=order_id,
                user_login=user_login
            )

            await publish_event(
                routing_key="coupon.applied",
                message_data={
                    "status": "SUCCESS",
                    "usageId": str(usage["_id"]),
                    "orderId": order_id,
                    "cartId": cart_id,
                    "couponCode": coupon["couponCode"],
                    "discountType": coupon.get("discountType"),
                    "discountValue": float(coupon.get("discountValue", 0)),
                    "appliedBy": user_login,
                    "processedAt": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            print(f" Error al registrar uso de cupón para la orden '{order_id}': {e}")
            # El uso no quedó registrado: devolvemos el lugar consumido en el paso 3
            await coupon_repository.release_usage(coupon["couponCode"])
            await publish_event(
                routing_key="coupon.failed",
                message_data={
                    "status": "ERROR",
                    "orderId": order_id,
                    "cartId": cart_id,
                    "couponCode": coupon_code,
                    "reason": str(e)
                }
            )

coupon_service = CouponService()