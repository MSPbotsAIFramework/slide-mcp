"""Non-credential configuration. Credentials are never read here — see api_client.py
and server.py, which take the per-request Slide API key from an HTTP header (SOP §3.1).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080
    slide_base_url: str = "https://api.slide.tech"


settings = Settings()
