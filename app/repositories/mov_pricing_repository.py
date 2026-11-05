from datetime import datetime
from app.database import get_database
from app.models.mov_pricing import MovPricingCreate

class MovPricingRepository:
    @property
    def collection(self):
        db = get_database()
        if db is None:
            raise RuntimeError("No hay conexión activa a la base de datos de MongoDB.")
        return db["mov_pricings"]

    async def create(self, mov_data: MovPricingCreate) -> dict:
        if not mov_data or not mov_data.pricingId:
            raise ValueError("No se puede registrar un movimiento de auditoría sin un 'pricingId' asociado.")

        doc = mov_data.model_dump()
        doc["creationDate"] = datetime.utcnow()
        
        result = await self.collection.insert_one(doc)
        if not result.inserted_id:
            raise RuntimeError("Error de persistencia: No se pudo guardar la auditoría en 'mov_pricings'.")

        doc["_id"] = str(result.inserted_id)
        return doc

mov_pricing_repository = MovPricingRepository()