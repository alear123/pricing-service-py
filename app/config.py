from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 8000
    MONGODB_URI: str = "mongodb://ec-mongo:27017"
    MONGODB_DB_NAME: str = "coupons_db"  
    
    RABBITMQ_URL: str = "amqp://guest:guest@ec-rabbitmq:5672/"
    RABBITMQ_EXCHANGE: str = "amq.direct"

    AUTHGO_URL: str = "http://prod-auth-go:3000"
    CARTGO_URL: str = "http://prod-cartgo-go:3003"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()