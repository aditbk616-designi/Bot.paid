import asyncio
import importlib
import logging
import subprocess
import sys
from html import escape
from io import BytesIO


# ─────────────── تثبيت المكاتب الناقصة تلقائياً ───────────────
REQUIRED = {
    "requests": "requests",
    "telegram": "python-telegram-bot",
    "PIL": "Pillow",
}


def ensure_packages():
    for module, pip_name in REQUIRED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"📦 تثبيت {pip_name} ...")
            cmd = [sys.executable, "-m", "pip", "install", pip_name]
            if subprocess.call(cmd) != 0:
                subprocess.check_call(cmd + ["--break-system-packages"])
    importlib.invalidate_caches()


ensure_packages()

import requests

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = "8986095323:AAEjDutbf6TIpp3mjzR6lgGRTy5fURW12fI"
DEV_URL = "https://t.me/spy_fk"
CHANNEL_URL = "https://t.me/LOKY_FF"


# ─────────────── الأزرار ───────────────
def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 المساعدة", callback_data="help"),
            InlineKeyboardButton("💡 مثال", callback_data="example"),
        ],
        [
            InlineKeyboardButton("👨‍💻 المطور", url=DEV_URL),
            InlineKeyboardButton("📢 القناة", url=CHANNEL_URL),
        ],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="menu")]
    ])


def result_menu(uid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 تحديث", callback_data=f"refresh:{uid}"),
            InlineKeyboardButton("🏠 القائمة", callback_data="menu"),
        ]
    ])


WELCOME_TEXT = (
    "أهلاً <b>{name}</b>! 👋\n\n"
    "🔥 مرحباً بك في بوت <b>معلومات Free Fire</b>\n"
    "أعرض لك <b>معلومات وبانر</b> أي حساب بسرعة ودقة.\n\n"
    "━━━━━━━━━━━━\n"
    "📌 <b>طريقة الاستخدام:</b>\n"
    "<code>/info ID</code>\n\n"
    "💡 <b>مثال:</b>\n"
    "<code>/info 555983270</code>\n"
    "━━━━━━━━━━━━"
)

HELP_TEXT = (
    "📖 <b>المساعدة</b>\n"
    "━━━━━━━━━━━━\n"
    "أرسل الأمر متبوعاً بالـ ID:\n"
    "<code>/info 555983270</code>\n\n"
    "راح يوصلك البانر + الاسم، المستوى، الإعجابات، الرتبة، الكلان وأكثر ✅"
)

EXAMPLE_TEXT = (
    "💡 <b>مثال</b>\n"
    "━━━━━━━━━━━━\n"
    "انسخ الأمر وأرسله:\n"
    "<code>/info 555983270</code>"
)


def welcome(user) -> str:
    return WELCOME_TEXT.format(name=escape(user.first_name or "صديقي"))


# ─────────────── الأوامر ───────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        welcome(update.effective_user),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        if query.message.photo:
            # رسالة النتيجة صورة، لا يمكن تعديلها كنص → نرسل قائمة جديدة
            await query.message.reply_text(
                welcome(query.from_user),
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu(),
            )
        else:
            await query.edit_message_text(
                welcome(query.from_user),
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu(),
            )
    elif data == "help":
        await query.edit_message_text(
            HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif data == "example":
        await query.edit_message_text(
            EXAMPLE_TEXT, parse_mode=ParseMode.HTML, reply_markup=back_menu()
        )
    elif data.startswith("refresh:"):
        uid = data.split(":", 1)[1]
        await send_profile(query.message, uid)


async def get_player_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ يرجى كتابة الـ ID بعد الأمر، مثال:\n<code>/info 8263375674</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=back_menu(),
        )
        return

    uid = context.args[0].strip()
    if not uid.isdigit():
        await update.message.reply_text("✨ يرجى إرسال أرقام الـ ID فقط.")
        return

    await send_profile(update.message, uid)


# ─────────────── جلب المعلومات ───────────────
def num(value, default=0) -> str:
    """تنسيق الأرقام بأمان (يتعامل مع النص أو None)"""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(default if value is None else value)


def fetch(url: str, timeout: int):
    return requests.get(url, timeout=timeout)


def prepare_banner(raw: bytes) -> BytesIO:
    """يعرض البانر كاملاً بدون قص: نضيف خلفية ضبابية حوله إذا كان عريضاً جداً"""
    out = BytesIO()
    out.name = "banner.jpg"
    try:
        from PIL import Image, ImageFilter

        img = Image.open(BytesIO(raw)).convert("RGB")
        img.thumbnail((1600, 1600))
        w, h = img.size

        max_ratio = 1.6  # أعرض نسبة عرض/طول يعرضها تيليجرام بدون قص
        if w / h > max_ratio:
            canvas_h = int(w / max_ratio)
            bg = img.resize((w, canvas_h)).filter(ImageFilter.GaussianBlur(25))
            bg.paste(img, (0, (canvas_h - h) // 2))
            img = bg

        img.save(out, format="JPEG", quality=92)
    except Exception:
        logging.exception("prepare_banner failed, using original image")
        out = BytesIO(raw)
        out.name = "banner.png"
    out.seek(0)
    return out


async def send_profile(message, uid: str):
    msg = await message.reply_text("⏳ جاري جلب البانر والمعلومات...")

    banner_api_url = f"https://nirob-free-fire-baner.vercel.app/profile?uid={uid}"
    info_api_url = f"https://das-ff-info.netlify.app/info?uid={uid}"

    try:
        info_response = await asyncio.to_thread(fetch, info_api_url, 10)

        if info_response.status_code != 200:
            await msg.edit_text("⚠️ تعذر الحصول على البيانات حالياً، حاول مجدداً.")
            return

        try:
            data = info_response.json()
        except ValueError:
            await msg.edit_text("⚠️ استجابة غير صالحة من السيرفر، حاول مجدداً.")
            return

        if not data.get("basicInfo"):
            await msg.edit_text("❌ لم يتم العثور على حساب بهذا الـ ID.")
            return

        basic = data.get("basicInfo", {})
        clan = data.get("clanBasicInfo", {})
        social = data.get("socialInfo", {})
        pet = data.get("petInfo", {})
        credit = data.get("creditScoreInfo", {})

        signature = escape(str(social.get("signature") or "").replace("\n", " ")) or "لا يوجد"
        nickname = escape(str(basic.get("nickname", "غير معروف")))
        clan_name = escape(str(clan.get("clanName", "لا يوجد")))

        caption = (
            f"🎯 <b>معلومات الحساب</b>\n"
            f"━━━━━━━━━━━━\n"
            f"👤 <b>الاسم:</b> <code>{nickname}</code>\n"
            f"🆔 <b>الـ ID:</b> <code>{basic.get('accountId', uid)}</code>\n"
            f"🌍 <b>السيرفر:</b> <code>{basic.get('region', 'N/A')}</code>\n"
            f"⭐ <b>المستوى:</b> <code>{basic.get('level', 0)}</code> "
            f"(EXP: <code>{num(basic.get('exp'))}</code>)\n"
            f"❤️ <b>الإعجابات:</b> <code>{num(basic.get('liked'))}</code>\n"
            f"🏆 <b>الرتبة (BR):</b> <code>{basic.get('rankingPoints', 0)}</code> نقطة\n"
            f"🎖️ <b>الرتبة (CS):</b> <code>{basic.get('csRankingPoints', 0)}</code> نقطة\n"
            f"💬 <b>التوقيع:</b> <code>{signature}</code>\n\n"
            f"🛡️ <b>الكلان</b>\n"
            f"├ <b>الاسم:</b> <code>{clan_name}</code>\n"
            f"├ <b>المستوى:</b> <code>{clan.get('clanLevel', '-')}</code>\n"
            f"└ <b>الأعضاء:</b> <code>{clan.get('memberNum', 0)}/{clan.get('capacity', 0)}</code>\n\n"
            f"🐾 <b>الحيوان الأليف:</b> مستوى <code>{pet.get('level', '-')}</code>\n"
            f"💯 <b>نقاط السلوك:</b> <code>{credit.get('creditScore', '-')}</code>"
        )

        try:
            banner_response = await asyncio.to_thread(fetch, banner_api_url, 15)
        except requests.exceptions.RequestException:
            banner_response = None
        await msg.delete()

        markup = result_menu(uid)

        if banner_response is not None and banner_response.status_code == 200 and banner_response.content:
            banner_bytes = await asyncio.to_thread(
                prepare_banner, banner_response.content
            )
            await message.reply_photo(
                photo=banner_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        else:
            await message.reply_text(
                caption, parse_mode=ParseMode.HTML, reply_markup=markup
            )

    except requests.exceptions.RequestException:
        await msg.edit_text("❌ حدث خطأ أثناء الاتصال بالسيرفرات.")
    except Exception:
        logging.exception("send_profile failed")
        await msg.edit_text("❌ حدث خطأ غير متوقع، حاول مجدداً.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", get_player_info))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🤖 البوت يعمل ومستعد لتلقي الأوامر...")
    app.run_polling()


if __name__ == "__main__":
    main()
