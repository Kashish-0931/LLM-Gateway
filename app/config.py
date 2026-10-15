from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_token: str = ""
    database_url: str = ""
    redis_url: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    class Config:
        env_file = ".env"

settings=Settings()