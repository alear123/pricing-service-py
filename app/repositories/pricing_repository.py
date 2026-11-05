from datetime import datetime
from typing import Optional
from app.database import get_database
from app.models.pricing import PricingCreate

class PricingRepository:
    @property
    def collection(self):
        db = get_database()
        if db is None:
            raise RuntimeError("No hay conexión activa a la base de datos de MongoDB.")
        return db["pricings"]

    async def get_by_article_id(self, article_id: str) -> Optional[dict]:
        if not article_id or not isinstance(article_id, str):
            raise ValueError("El parámetro 'article_id' en el repositorio debe ser un string válido.")
        
        return await self.collection.find_one({"articleId": article_id})

    async def create(self, pricing_data: PricingCreate) -> dict:
        if not pricing_data or not pricing_data.articleId:
            raise ValueError("Imposible crear registro de Pricing sin 'articleId'.")
        if pricing_data.price is None or pricing_data.price < 0:
            raise ValueError("Imposible crear registro de Pricing con valor de precio inválido.")

        now = datetime.utcnow()
        doc = {
            "articleId": pricing_data.articleId,
            "price": float(pricing_data.price),
            "creationDate": now,
            "updateDate": now
        }
        result = await self.collection.insert_one(doc)
        if not result.inserted_id:
            raise RuntimeError("Error de base de datos: La operación de inserción no devolvió un BSON ID.")

        doc["_id"] = str(result.inserted_id)
        return doc

    async def update_price(self, article_id: str, new_price: float) -> Optional[dict]:
        if not article_id or not isinstance(article_id, str):
            raise ValueError("Se requiere un 'article_id' válido para actualizar en la base de datos.")
        if new_price is None or new_price < 0:
            raise ValueError("El precio a actualizar en la colección debe ser un número real positivo o cero.")

        now = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"articleId": article_id},
            {
                "$set": {
                    "price": float(new_price),
                    "updateDate": now
                }
            },
            return_document=True
        )
        
        if not result:
            raise RuntimeError(f"No se encontró el documento para el artículo '{article_id}' durante la actualización.")

        result["_id"] = str(result["_id"])
        return result

pricing_repository = PricingRepository()