from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv(Path(__file__).resolve().parent / ".env")


class Settings(BaseSettings):
    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # Nova Act
    nova_act_api_key: str = ""

    # App
    app_env: str = "development"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    # Browser automation
    headless_browser: bool = True
    max_concurrent_browsers: int = 3
    browser_timeout_seconds: int = 60

    # Rate limits
    max_tasks_per_minute: int = 10
    max_concurrent_tasks: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def has_aws_credentials(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    @property
    def has_nova_act_key(self) -> bool:
        return bool(self.nova_act_api_key)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
