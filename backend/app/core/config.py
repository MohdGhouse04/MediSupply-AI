from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "MediSupply AI"
    APP_ENV: str = "development"
    DATABASE_URL: str

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    FRONTEND_ORIGINS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
