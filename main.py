import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import connect_to_mongo, close_mongo_connection
from app.rabbitmq import (
    connect_to_rabbitmq, 
    close_rabbitmq_connection, 
    start_order_consumer
)
from app.config import settings
from app.repositories.coupon_repository import coupon_repository  #  Importamos el repositorio

# Importamos los controladores
from app.controllers.pricing_controller import router as pricing_router
from app.controllers.coupon_controller import router as coupon_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    
    #  Creamos el índice TTL para expirar reservas temporales a los 30 min (1800 segundos)
    try:
        await coupon_repository.pending_coupons_col.create_index(
            "created_at", 
            expireAfterSeconds=1800
        )
        print(" Índice TTL para cupones pendientes configurado (30 min).")
    except Exception as e:
        print(f" Error al asegurar el índice TTL: {e}")

    await connect_to_rabbitmq()
    
    # Iniciamos el listener de RabbitMQ en segundo plano
    await start_order_consumer()
    
    yield
    # Shutdown
    await close_mongo_connection()
    await close_rabbitmq_connection()

app = FastAPI(
    title="Pricing Microservice",
    version="1.0.0",
    lifespan=lifespan
)

# Registramos los endpoints
app.include_router(pricing_router)
app.include_router(coupon_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pricing-service-py"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)