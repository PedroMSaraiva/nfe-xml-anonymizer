from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    presidio_url: str = "http://presidio:8080"

    model_config = {"env_prefix": ""}


settings = Settings()
