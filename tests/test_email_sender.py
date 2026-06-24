from pathlib import Path
from types import SimpleNamespace

import pytest

from market_info.notify.email_sender import EmailSendError, send_report_email


TEST_PASSWORD = "test-password-placeholder"


class FakeSMTPBase:
    instances: list["FakeSMTPBase"] = []

    def __init__(self, host: str, port: int, timeout: float | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = None
        self.sent_messages = []
        FakeSMTPBase.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        self.logged_in = (user, password)

    def send_message(self, message, from_addr: str, to_addrs: list[str]) -> None:
        self.sent_messages.append(
            {
                "message": message,
                "from_addr": from_addr,
                "to_addrs": to_addrs,
            }
        )


class FakeSMTP(FakeSMTPBase):
    instances: list[FakeSMTPBase] = []

    def __init__(self, host: str, port: int, timeout: float | None = None):
        super().__init__(host, port, timeout=timeout)
        FakeSMTP.instances.append(self)


class FakeSMTPSSL(FakeSMTPBase):
    instances: list[FakeSMTPBase] = []

    def __init__(self, host: str, port: int, timeout: float | None = None):
        super().__init__(host, port, timeout=timeout)
        FakeSMTPSSL.instances.append(self)


def make_settings(**overrides):
    values = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_user": "sender@example.com",
        "smtp_password": TEST_PASSWORD,
        "mail_from": "reports@example.com",
        "mail_to": "owner@example.com",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def install_settings(monkeypatch, settings) -> None:
    monkeypatch.setattr("market_info.notify.email_sender.Settings", lambda: settings)


def install_smtp(monkeypatch) -> None:
    FakeSMTP.instances.clear()
    FakeSMTPSSL.instances.clear()
    FakeSMTPBase.instances.clear()
    monkeypatch.setattr("market_info.notify.email_sender.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("market_info.notify.email_sender.smtplib.SMTP_SSL", FakeSMTPSSL)


def make_report(tmp_path: Path, name: str = "市场周报.xlsx") -> Path:
    report_path = tmp_path / name
    report_path.write_bytes(b"xlsx-content")
    return report_path


def make_summary() -> dict[str, object]:
    return {
        "新增项目数": 3,
        "merged_projects": 2,
        "疑似重复待复核数": 1,
        "project_total": 10,
        "status_events": 4,
        "generated_at": "2026-06-24 10:00:00",
    }


def last_sent_message():
    smtp = FakeSMTPSSL.instances[-1] if FakeSMTPSSL.instances else FakeSMTP.instances[-1]
    return smtp.sent_messages[-1]["message"]


def test_send_report_email_builds_utf8_chinese_subject_body_and_xlsx_attachment(
    monkeypatch,
    tmp_path,
) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings())
    report_path = make_report(tmp_path, "市场信息周报.xlsx")

    send_report_email(report_path, make_summary())

    message = last_sent_message()
    assert "市场信息自动收集周报" in str(message["Subject"])
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "新增项目数：3" in body
    assert "合并/更新项目数：2" in body
    assert "疑似重复待复核数：1" in body
    assert "项目台账总数：10" in body
    assert "状态变化事件数：4" in body
    assert "Excel 文件名：市场信息周报.xlsx" in body
    assert "生成时间：2026-06-24 10:00:00" in body
    assert message.get_content_charset() is None

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.get_content_type() == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert attachment.get_filename() == "市场信息周报.xlsx"
    assert attachment.get_payload(decode=True) == b"xlsx-content"


def test_smtp_port_465_uses_smtp_ssl(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings(smtp_port=465))

    send_report_email(make_report(tmp_path), make_summary())

    assert len(FakeSMTPSSL.instances) == 1
    assert len(FakeSMTP.instances) == 0
    smtp = FakeSMTPSSL.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 465
    assert smtp.timeout == 30
    assert smtp.started_tls is False
    assert smtp.logged_in == ("sender@example.com", TEST_PASSWORD)


def test_smtp_port_587_uses_starttls(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings(smtp_port=587))

    send_report_email(make_report(tmp_path), make_summary())

    assert len(FakeSMTPSSL.instances) == 0
    assert len(FakeSMTP.instances) == 1
    assert FakeSMTP.instances[0].started_tls is True
    assert FakeSMTP.instances[0].timeout == 30


def test_non_tls_smtp_port_is_rejected_before_login(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings(smtp_port=25))

    with pytest.raises(EmailSendError, match="SMTP_PORT"):
        send_report_email(make_report(tmp_path), make_summary())

    assert FakeSMTP.instances == []
    assert FakeSMTPSSL.instances == []


def test_mail_to_supports_comma_separated_recipients(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(
        monkeypatch,
        make_settings(mail_to=" owner@example.com, ops@example.com ,, boss@example.com "),
    )

    send_report_email(make_report(tmp_path), make_summary())

    sent = FakeSMTPSSL.instances[0].sent_messages[0]
    assert sent["from_addr"] == "reports@example.com"
    assert sent["to_addrs"] == [
        "owner@example.com",
        "ops@example.com",
        "boss@example.com",
    ]


def test_missing_required_config_raises_business_error_without_password(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings(smtp_host="", smtp_password=TEST_PASSWORD))

    with pytest.raises(EmailSendError) as exc_info:
        send_report_email(make_report(tmp_path), make_summary())

    assert "SMTP_HOST" in str(exc_info.value)
    assert TEST_PASSWORD not in str(exc_info.value)


def test_missing_attachment_raises_business_error(monkeypatch, tmp_path) -> None:
    install_smtp(monkeypatch)
    install_settings(monkeypatch, make_settings())

    with pytest.raises(EmailSendError) as exc_info:
        send_report_email(tmp_path / "missing.xlsx", make_summary())

    assert "Report file does not exist" in str(exc_info.value)
    assert TEST_PASSWORD not in str(exc_info.value)


def test_smtp_failure_raises_business_error_without_password(monkeypatch, tmp_path) -> None:
    class FailingSMTPSSL(FakeSMTPSSL):
        def login(self, user: str, password: str) -> None:
            raise RuntimeError(f"failed with {password}")

    install_smtp(monkeypatch)
    monkeypatch.setattr("market_info.notify.email_sender.smtplib.SMTP_SSL", FailingSMTPSSL)
    install_settings(monkeypatch, make_settings())

    with pytest.raises(EmailSendError) as exc_info:
        send_report_email(make_report(tmp_path), make_summary())

    assert "SMTP email send failed" in str(exc_info.value)
    assert TEST_PASSWORD not in str(exc_info.value)
