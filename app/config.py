from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_token: str = ""
    database_url: str = ""
    redis_url: str = ""
    class Config:
        env_file = ".env"

settings=Settings()