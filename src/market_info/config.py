from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = Field(
        default="postgresql+psycopg://market_info:market_info@localhost:5432/market_info",
        alias="DATABASE_URL",
    )
    wechat_exporter_base_url: str = Field(
        default="http://localhost:3000",
        alias="WECHAT_EXPORTER_BASE_URL",
    )
    wechat_exporter_auth_key: str = Field(default="", alias="WECHAT_EXPORTER_AUTH_KEY")
    accounts_config_path: str = Field(
        default="config/accounts.yml",
        alias="ACCOUNTS_CONFIG_PATH",
    )
    ai_base_url: str = Field(default="", alias="AI_BASE_URL")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_extraction_model: str = Field(default="", alias="AI_EXTRACTION_MODEL")
    ai_embedding_model: str = Field(default="", alias="AI_EMBEDDING_MODEL")
    embedding_dim: int = Field(default=1536, alias="EMBEDDING_DIM")
    ai_concurrency: int = Field(default=3, ge=1, le=10, alias="AI_CONCURRENCY")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    mail_from: str = Field(default="", alias="MAIL_FROM")
    mail_to: str = Field(default="", alias="MAIL_TO")
    mail_cc: str = Field(default="", alias="MAIL_CC")
    wecom_webhook_url: str = Field(default="", alias="WECOM_WEBHOOK_URL")
    export_dir: str = Field(default="exports", alias="EXPORT_DIR")


class AccountConfig(BaseModel):
    name: str
    fakeid: str
    enabled: bool = True


def load_accounts_config(path: Path) -> list[AccountConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("accounts config root must be a mapping")
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("accounts must be a list")
    return [AccountConfig(**item) for item in accounts]
