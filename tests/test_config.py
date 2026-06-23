from pathlib import Path

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
