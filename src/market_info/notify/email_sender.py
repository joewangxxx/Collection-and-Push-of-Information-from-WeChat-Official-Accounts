import smtplib
from email.message import EmailMessage
from pathlib import Path

from market_info.config import Settings


XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EMAIL_SUBJECT = "市场信息自动收集周报"


class EmailSendError(Exception):
    """Raised when report email configuration or SMTP sending fails."""


SMTP_TIMEOUT_SECONDS = 30


def send_report_email(report_path: Path, summary: dict[str, object]) -> None:
    settings = Settings()
    recipients = _parse_recipients(settings.mail_to)
    _validate_settings(settings, recipients)

    if not report_path.is_file():
        raise EmailSendError(f"Report file does not exist: {report_path}")

    message = _build_message(settings.mail_from, recipients, report_path, summary)
    _send_message(settings, recipients, message)


def _validate_settings(settings: Settings, recipients: list[str]) -> None:
    missing = []
    if not _present(settings.smtp_host):
        missing.append("SMTP_HOST")
    if settings.smtp_port is None:
        missing.append("SMTP_PORT")
    if not _present(settings.smtp_user):
        missing.append("SMTP_USER")
    if not _present(settings.smtp_password):
        missing.append("SMTP_PASSWORD")
    if not _present(settings.mail_from):
        missing.append("MAIL_FROM")
    if not recipients:
        missing.append("MAIL_TO")

    if missing:
        raise EmailSendError(f"Missing required email config: {', '.join(missing)}")
    if settings.smtp_port not in (465, 587):
        raise EmailSendError("SMTP_PORT must be 465 for SSL or 587 for STARTTLS.")


def _build_message(
    mail_from: str,
    recipients: list[str],
    report_path: Path,
    summary: dict[str, object],
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = EMAIL_SUBJECT
    message["From"] = mail_from
    message["To"] = ", ".join(recipients)
    message.set_content(_build_body(report_path, summary), charset="utf-8")

    message.add_attachment(
        report_path.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=report_path.name,
    )
    return message


def _build_body(report_path: Path, summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "市场信息自动收集周报运行摘要",
            "",
            f"新增项目数：{_summary_value(summary, '新增项目数', 'new_projects')}",
            f"合并/更新项目数：{_summary_value(summary, '合并/更新项目数', 'merged_projects')}",
            f"疑似重复待复核数：{_summary_value(summary, '疑似重复待复核数', 'review_projects')}",
            f"项目台账总数：{_summary_value(summary, '项目台账总数', 'project_total')}",
            f"状态变化事件数：{_summary_value(summary, '状态变化事件数', 'status_events')}",
            f"Excel 文件名：{report_path.name}",
            f"生成时间：{_summary_value(summary, '生成时间', 'generated_at')}",
            "",
        ]
    )


def _send_message(
    settings: Settings,
    recipients: list[str],
    message: EmailMessage,
) -> None:
    smtp_class = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    try:
        with smtp_class(
            settings.smtp_host,
            settings.smtp_port,
            timeout=SMTP_TIMEOUT_SECONDS,
        ) as smtp:
            if settings.smtp_port == 587:
                smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(
                message,
                from_addr=settings.mail_from,
                to_addrs=recipients,
            )
    except Exception as exc:
        raise EmailSendError("SMTP email send failed.") from exc


def _parse_recipients(mail_to: str) -> list[str]:
    return [item.strip() for item in (mail_to or "").split(",") if item.strip()]


def _summary_value(summary: dict[str, object], chinese_key: str, english_key: str) -> str:
    value = summary.get(chinese_key, summary.get(english_key, ""))
    if value is None:
        return ""
    return str(value)


def _present(value: object) -> bool:
    return bool(str(value).strip()) if value is not None else False
