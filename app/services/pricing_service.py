from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from app.repositories.pricing_repository import pricing_repository
from app.repositories.mov_pricing_repository import mov_pricing_repository
from app.models.pricing import PricingCreate
from app.models.mov_pricing import MovPricingCreate, MovType
from app.models.events import PriceUpdatedEvent, PriceQueriedEvent
from app.rabbitmq import publish_event

class PricingService:

    async def get_price(self, article_id: str) -> dict:
        # Validar regla de negocio/contrato
        if not article_id or not isinstance(article_id, str):
            raise ValueError("El identificador del artículo debe ser una cadena válida.")

        pricing = await pricing_repository.get_by_article_id(article_id)
        if not pricing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró precio para el artículo '{article_id}'"
            )

        if "_id" in pricing:
            pricing["_id"] = str(pricing["_id"])

        event = PriceQueriedEvent(
            timestamp=datetime.utcnow(),
            articleId=article_id
        )
        await publish_event("pricing.queried", event.model_dump())

        return pricing

    async def create_or_update_price(
        self, 
        pricing_data: PricingCreate, 
        mov_type: MovType = MovType.SET,
        user_login: Optional[str] = None  
    ) -> dict:
        # 1. Validaciones de negocio del Payload
        if not pricing_data or not pricing_data.articleId:
            raise ValueError("Los datos de pricing deben incluir un 'articleId' válido.")

        if pricing_data.price < 0:
            raise ValueError("El valor del precio o delta no puede ser negativo.")

        if not user_login:
            raise ValueError("Se requiere un 'user_login' válido para registrar la auditoría.")

        existing = await pricing_repository.get_by_article_id(pricing_data.articleId)

        if not existing:
            # Regla de negocio: No se puede decrementar un artículo sin historial previo
            if mov_type == MovType.DECR:
                raise ValueError(
                    f"No es posible decrementar el artículo '{pricing_data.articleId}' porque no existe un precio registrado previamente."
                )
            
            updated_pricing = await pricing_repository.create(pricing_data)
            new_price = pricing_data.price
        else:
            current_price = float(existing.get("price", 0.0))
            
            if mov_type == MovType.SET:
                new_price = pricing_data.price
            elif mov_type == MovType.INCR:
                new_price = current_price + pricing_data.price
            elif mov_type == MovType.DECR:
                new_price = current_price - pricing_data.price
                # Regla de negocio: El precio resultante no puede ser negativo
                if new_price < 0:
                    raise ValueError(
                        f"El decremento solicitado ({pricing_data.price}) supera el precio actual ({current_price}). El precio no puede ser inferior a 0.0."
                    )

            updated_pricing = await pricing_repository.update_price(pricing_data.articleId, new_price)

        if not updated_pricing or "_id" not in updated_pricing:
            raise RuntimeError("Fallo crítico: No se pudo obtener la entidad 'Pricing' tras la actualización.")

        # Auditoría de movimientos
        await mov_pricing_repository.create(MovPricingCreate(
            pricingId=str(updated_pricing["_id"]),
            movType=mov_type,
            value=pricing_data.price,
            userLogin=user_login 
        ))

        # Evento de actualización
        event = PriceUpdatedEvent(
            timestamp=datetime.utcnow(),
            articleId=pricing_data.articleId,
            price=new_price
        )
        await publish_event("pricing.updated", event.model_dump())

        return updated_pricing

pricing_service = PricingService()