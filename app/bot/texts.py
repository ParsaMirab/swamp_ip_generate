"""All user facing texts, kept in one place.

Every dynamic value is escaped before it is embedded, because the messages are
sent with ``ParseMode.HTML``.
"""

from __future__ import annotations

from html import escape

WELCOME = (
    "به Swamp IP Generator خوش آمدید 🌐\n\n"
    "لطفاً Config مورد نظر خود را ارسال کنید."
)

NOT_ADMIN = "⛔ شما به پنل مدیریت دسترسی ندارید."

ADMIN_CALLBACK_EXPIRED = "این دکمه دیگر معتبر نیست. دستور /admin را ارسال کنید."

CANCELLED = "لغو شد."

INVALID_CONFIG = "❌ Config نامعتبر است.\nلطفاً یک Config معتبر ارسال کنید."

UNSUPPORTED_CONFIG = "❌ این نوع Config در حال حاضر پشتیبانی نمیشود."

NO_IP_CONFIGURED = "❌ هنوز IP توسط Admin تنظیم نشده است."

INTERNAL_ERROR = "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید."

UNKNOWN_COMMAND = (
    "دستور مورد نظر پیدا نشد.\n\n"
    "برای دریافت Config، کافی است Config خود را ارسال کنید.\n"
    "برای شروع دستور /start را ارسال کنید."
)

ASK_FOR_IP = (
    "IP جدید را وارد کنید:\n\n"
    "مثال:\n144.31.157.131\n\n"
    "توجه: فقط IP یا Domain را وارد کنید و Port را وارد نکنید.\n"
    "برای لغو دستور /cancel را ارسال کنید."
)


def code(value: str) -> str:
    """Wrap a value in an HTML code block (tap to copy on Telegram)."""
    return f"<code>{escape(value)}</code>"


def admin_panel(current_host: str | None) -> str:
    current = code(current_host) if current_host else "<i>تنظیم نشده</i>"
    return (
        "🛠 پنل مدیریت Swamp IP Generator\n\n"
        f"IP فعلی:\n{current}\n\n"
        "یک گزینه را انتخاب کنید:"
    )


def ip_saved(host: str) -> str:
    return f"✅ IP با موفقیت تغییر کرد.\n\nIP فعلی:\n{code(host)}"


def invalid_ip(reason: str) -> str:
    return (
        f"❌ IP نامعتبر است.\n{escape(reason)}\n\n"
        "لطفاً یک IP یا Domain معتبر وارد کنید یا دستور /cancel را ارسال کنید."
    )


def config_ready(config: str) -> str:
    return f"✅ Config شما آماده شد:\n\n{code(config)}"
