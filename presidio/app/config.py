from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hash_salt: str = "sefaz-go-dev-salt-change-in-production"
    dp_epsilon: float = 2.0
    spacy_model: str = "en_core_web_lg"

    model_config = {"env_prefix": "ANON_"}


settings = Settings()
