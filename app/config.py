from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, overridable via environment or .env file."""

    comfy_url: str = "http://sd:8188"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "local-key"
    output_dir: str = "output"
    base_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()