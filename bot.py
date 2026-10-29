import os
import logging
import threading
import re
import random
import asyncio
import datetime
from zoneinfo import ZoneInfo

from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- Настройки из переменных окружения ---
TOKEN = os.environ.get("BOT_TOKEN")
GROUP_1_ID = int(os.environ.get("GROUP_1_ID", "0"))
GROUP_2_ID = int(os.environ.get("GROUP_2_ID", "0"))

# --- Триггеры и ответы ---
TRIGGERS = {
    "норма": (
        " ✦ норма активности:\n"
        "• 100 сообщений в неделю\n"
        "• 200 сообщений в неделю для админов\n"
        "• для ролевиков с учётом 2 постов в неделю норма снижается до 40 сообщений\n"
        "• чистка в воскресенье в 19:00 по московскому времени"
    ),
    "дискорд": " ✦ ссылка на наш Discord-сервер: https://discord.gg/t6y6Tbg8Ew",
    "рест": (
        " ✦ чтобы взять рест, обратитесь к владельцу.\n"
        "внимание: взять рест можно только на две недели. "
        "бывают исключения на бессрочный рест из-за срочных причин."
    ),
    "майнкрафт": (
        " ✦ версия нашего Minecraft-сервера: 1.21.6\n"
        "Адрес: matrix-hCsi.aternos.me:47280\n"
        "Для включения обратитесь к Итто."
    ),
    "инициалы": " ✦ если вы очень патриотичны, можете поставить инициал MX.",
    "хуйня": "не выражайся",
}

EMOJIS = [
    "🌊", "🪐", "⭐️", "🌙", "☁️", "🌫️", "🌄", "🌌", "🎆", "🔮", "💌",
    "🩷", "🤍", "🖤", "🩶", "💜", "💖", "🎐", "🗝️", "⛓️", "💎", "🌠",
    "🎼", "🍒", "✨", "⚡️", "🌷", "🪷", "🐇", "🦢", "🕊️", "🌂", "🕯️",
    "🎀", "💿", "🗻", "🪽", "🕸️", "🪼", "🐁", "🐚", "❄️", "🌬️", "🫧",
]


logging.basicConfig(level=logging.INFO)

# --- Flask-заглушка, чтобы Render не ругался на отсутствие порта ---
flask_app = Flask(__name__)

@flask_app.route("/")
@flask_app.route("/health")
def health():
    return "Bot is running", 200

# --- 1. Приветствие новичков в группе ---
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if not member.is_bot:
            text = (
                f"добро пожаловать в Matrix, {member.first_name}! "
                "надеюсь, вам здесь понравится и вы приживетесь🩷\n\n"
                "если у вас возникнут трудности или вопросы, в любой момент "
                "вы можете обратиться к нашей администрации, она рада вам помочь.\n\n"
                "несколько вопросов для знакомства:\n"
                "– как к вам обращаться?\n"
                "– какие у вас увлечения?\n"
                "– как проходит день?\n\n"
                "в чате существуют автоматические ответы, список: "
                "норма, дискорд, инициалы, майнкрафт, рест."
            )
            await update.message.reply_text(text)

# --- 2. Триггеры в Группе 1 ---
async def triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat.id != GROUP_1_ID:
        return
    text = update.message.text.lower().strip().strip("!?.,… ")
    answer = TRIGGERS.get(text)
    if answer:
        await update.message.reply_text(answer)


# --- 3. Приветствие в ЛС по /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "доброго времени суток! здесь вы можете оставить заявку или жалобу. наши администраторы ответят вам как можно скорее."
    )

# --- 4. Пересылка ЛС в Группу 2 + подтверждение ---
async def forward_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message.text:
        return

    user = update.effective_user
    username = f"@{user.username}" if user.username else "без username"
    msg = (
        f"📩 от {user.full_name} ({username}) [ID:{user.id}]:\n\n"
        f"{update.message.text}\n\n"
        "➤ чтобы ответить, сделайте реплай на это сообщение."
    )
    try:
        sent = await context.bot.send_message(chat_id=GROUP_2_ID, text=msg)
        context.bot_data.setdefault("threads", {})[sent.message_id] = user.id
    except Exception as e:
        logging.error(f"ошибка пересылки: {e}")

    await update.message.reply_text("ваше сообщение дошло до администраторов ♡. среднее время ожидания ответа – 10 минут.")

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    original = msg.reply_to_message
    if not original or not msg.text:
        return

    threads = context.bot_data.setdefault("threads", {})

    user_id = None
    if original.text:
        match = re.search(r"\[ID:(\d+)\]", original.text)
        if match:
            user_id = int(match.group(1))

    if user_id is None:
        user_id = threads.get(original.message_id)

    if user_id is None:
        return

    threads[msg.message_id] = user_id

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=msg.text,
        )
        await msg.reply_text("ответ доставлен. ✰")
    except Exception as e:
        logging.error(f"ошибка ответа: {e}")
        await msg.reply_text("не удалось отправить (возможно, человек заблокировал бота).")

# --- 6. Запоминаем, кто писал в Группе 1 ---
async def track_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and not user.is_bot:
        context.bot_data.setdefault("members", {})[user.id] = user.first_name

# --- 7. Тег всех, кто писал (пачками по 5) ---
async def tag_all(context: ContextTypes.DEFAULT_TYPE, chat_id: int, header: str = ""):
    ids = list(context.bot_data.get("members", {}))
    if not ids:
        return

    emojis = EMOJIS[:]
    random.shuffle(emojis)

    if header:
        await context.bot.send_message(chat_id=chat_id, text=header)
    for i in range(0, len(ids), 5):
        mentions = " ".join(
            f'<a href="tg://user?id={uid}">{emojis[(i + n) % len(emojis)]}</a>'
            for n, uid in enumerate(ids[i:i + 5])
        )
        await context.bot.send_message(chat_id=chat_id, text=mentions, parse_mode="HTML")
        await asyncio.sleep(0.5)

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id != GROUP_1_ID:
        return
    member = await chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        return
    await tag_all(context, chat.id)

# --- 8. Напоминание о чистке ---
async def cleanup_reminder(context: ContextTypes.DEFAULT_TYPE):
    await tag_all(
        context,
        GROUP_1_ID,
        "cегодня в 19:00 по мск чистка. проверьте свою норму активности.",
    )

# --- Созыв по слову «калл» ---
async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat = update.effective_chat
    member = await chat.get_member(update.effective_user.id)
    if member.status not in ("administrator", "creator"):
        return

    text = update.message.text.strip()[4:].strip()  # всё после «калл»
    header = f"📢 {text}" if text else ""
    await tag_all(context, chat.id, header)

# --- Запуск ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.Chat(GROUP_1_ID), track_members), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(GROUP_1_ID) & ~filters.UpdateType.EDITED_MESSAGE,
            triggers,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(r"(?i)^калл(\s|$)") & filters.Chat(GROUP_1_ID) & ~filters.UpdateType.EDITED_MESSAGE,
            call_command,
        ),
        group=1,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            forward_dm,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(GROUP_2_ID) & filters.REPLY,
            admin_reply,
        )
    )

    app.job_queue.run_daily(
        cleanup_reminder,
        time=datetime.time(12, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        days=(0,),
    )

    async def on_error(update, context):
        logging.error("Ошибка в боте", exc_info=context.error)

    app.add_error_handler(on_error)
    app.run_polling(drop_pending_updates=True, bootstrap_retries=-1)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    main()
