
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

class Database:
    client: AsyncIOMotorClient = None

db = Database()

async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    print("Conectado exitosamente a MongoDB")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        print("Conexión a MongoDB cerrada")

def get_database():
    return db.client[settings.MONGODB_DB_NAME]