from pathlib import Path

import pytest
from pydantic import ValidationError

from market_info.config import Settings
from market_info.config import load_accounts_config


def test_load_accounts_config_reads_one_account(tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text(
        """
accounts:
  - name: "测试公众号"
    fakeid: "fakeid123"
    enabled: true
""",
        encoding="utf-8",
    )

    accounts = load_accounts_config(config_path)

    assert len(accounts) == 1
    assert accounts[0].name == "测试公众号"
    assert accounts[0].fakeid == "fakeid123"
    assert accounts[0].enabled is True


def test_load_accounts_config_returns_empty_list_for_empty_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text("", encoding="utf-8")

    assert load_accounts_config(config_path) == []


def test_load_accounts_config_rejects_non_mapping_root(tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a mapping"):
        load_accounts_config(config_path)


def test_load_accounts_config_rejects_non_list_accounts(tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text("accounts: fakeid123", encoding="utf-8")

    with pytest.raises(ValueError, match="accounts must be a list"):
        load_accounts_config(config_path)


def test_load_accounts_config_defaults_enabled_to_true(tmp_path: Path) -> None:
    config_path = tmp_path / "accounts.yml"
    config_path.write_text(
        """
accounts:
  - name: "默认启用公众号"
    fakeid: "fakeid456"
""",
        encoding="utf-8",
    )

    accounts = load_accounts_config(config_path)

    assert len(accounts) == 1
    assert accounts[0].enabled is True


def test_settings_ai_concurrency_defaults_to_three(monkeypatch) -> None:
    monkeypatch.delenv("AI_CONCURRENCY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ai_concurrency == 3


def test_settings_ai_concurrency_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("AI_CONCURRENCY", "5")

    settings = Settings(_env_file=None)

    assert settings.ai_concurrency == 5


@pytest.mark.parametrize("value", ["0", "11"])
def test_settings_ai_concurrency_is_limited(monkeypatch, value: str) -> None:
    monkeypatch.setenv("AI_CONCURRENCY", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
