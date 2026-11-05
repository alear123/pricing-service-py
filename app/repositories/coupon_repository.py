from datetime import datetime
from typing import Optional, Any
from app.database import get_database
from app.models.coupon import CouponCreate, CouponUpdate

class CouponRepository:

    @property
    def coupons_col(self):
        db = get_database()
        if db is None:
            raise RuntimeError("Base de datos no inicializada.")
        return db["coupons"]

    @property
    def usages_col(self):
        db = get_database()
        if db is None:
            raise RuntimeError("Base de datos no inicializada.")
        return db["coupon_usages"]

    @property
    def pending_coupons_col(self):
        db = get_database()
        if db is None:
            raise RuntimeError("Base de datos no inicializada.")
        return db["pending_coupons"]

    async def get_by_code(self, coupon_code: str) -> Optional[dict]:
        if not coupon_code or not isinstance(coupon_code, str):
            raise ValueError("El parámetro 'coupon_code' debe ser una cadena válida en el repositorio.")

        doc = await self.coupons_col.find_one({"couponCode": coupon_code})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def create(self, coupon_data: CouponCreate) -> dict:
        if not coupon_data or not coupon_data.couponCode:
            raise ValueError("No se puede crear un cupón con datos nulos o sin 'couponCode'.")

        doc = coupon_data.model_dump()
        doc["couponCode"] = doc["couponCode"].strip()
        doc["creationDate"] = datetime.utcnow()

        result = await self.coupons_col.insert_one(doc)
        if not result.inserted_id:
            raise RuntimeError("Error de la base de datos: La inserción del cupón falló.")

        doc["_id"] = str(result.inserted_id)
        return doc

    async def update(self, coupon_code: str, update_data: CouponUpdate) -> Optional[dict]:
        if not coupon_code or not isinstance(coupon_code, str):
            raise ValueError("Se requiere un 'coupon_code' válido para actualizar en el repositorio.")

        fields_to_update = {k: v for k, v in update_data.model_dump().items() if v is not None}
        if not fields_to_update:
            return await self.get_by_code(coupon_code)

        result = await self.coupons_col.find_one_and_update(
            {"couponCode": coupon_code},
            {"$set": fields_to_update},
            return_document=True
        )
        if result:
            result["_id"] = str(result["_id"])
        return result

    async def count_usages(self, coupon_id: Any) -> int:
        if not coupon_id:
            raise ValueError("El 'coupon_id' es obligatorio para contar los usos.")

        return await self.usages_col.count_documents({"couponId": str(coupon_id)})

    async def is_applied_to_cart(self, cart_id: str) -> bool:
        if not cart_id or not isinstance(cart_id, str):
            raise ValueError("El 'cart_id' es obligatorio para verificar si ya fue aplicado.")

        usage = await self.usages_col.find_one({"cartId": str(cart_id)})
        return usage is not None

    async def register_usage(
        self, 
        coupon_id: Any, 
        cart_id: str, 
        order_id: Optional[str] = None,
        user_login: Optional[str] = None
    ) -> dict:
        if not coupon_id or not cart_id:
            raise ValueError("Se requieren 'coupon_id' y 'cart_id' válidos para registrar el uso.")

        usage_doc = {
            "couponId": str(coupon_id),
            "cartId": str(cart_id),
            "orderId": str(order_id) if order_id else None,
            "usedOn": datetime.utcnow(),
            "usedBy": user_login
        }
        
        result = await self.usages_col.insert_one(usage_doc)
        if not result.inserted_id:
            raise RuntimeError("Error de persistencia: No se pudo insertar el registro en 'coupon_usages'.")

        usage_doc["_id"] = str(result.inserted_id)
        return usage_doc

    async def save_pending_coupon(self, cart_id: str, coupon_code: str, user_login: Optional[str] = None) -> None:
        if not cart_id or not coupon_code:
            raise ValueError("Los campos 'cart_id' y 'coupon_code' son obligatorios para guardar un cupón pendiente.")

        await self.pending_coupons_col.update_one(
            {"cart_id": str(cart_id)},
            {
                "$set": {
                    "cart_id": str(cart_id),
                    "coupon_code": str(coupon_code).strip(),
                    "user_login": user_login,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def get_and_delete_pending_coupon(self, cart_id: str, user_id: str) -> Optional[dict]:
        if not cart_id and not user_id:
            raise ValueError("Se requiere al menos 'cart_id' o 'user_id' para buscar la reserva pendiente.")

        query = []
        if cart_id:
            query.append({"cart_id": str(cart_id)})
        if user_id:
            query.append({"user_login": str(user_id)})

        pending = await self.pending_coupons_col.find_one({"$or": query})
        if pending:
            await self.pending_coupons_col.delete_one({"_id": pending["_id"]})
            pending["_id"] = str(pending["_id"])
        return pending

coupon_repository = CouponRepository()