import os
import logging
import threading
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
        "📊 Норма активности:\n"
        "• 100 сообщений в неделю\n"
        "• 200 сообщений в неделю для админов\n"
        "• Для ролевиков с учётом 2 постов в неделю норма снижается до 40 сообщений\n"
        "• Чистка в воскресенье в 19:00 по московскому времени"
    ),
    "дискорд": "🔗 Ссылка на наш Discord-сервер: https://discord.gg/t6y6Tbg8Ew",
    "рест": (
        "🛌 Чтобы взять рест, обратитесь к владельцу.\n"
        "Внимание: взять рест можно только на две недели. "
        "Бывают исключения на бессрочный рест."
    ),
    "майнкрафт": (
        "⛏️ Версия нашего Minecraft-сервера: 1.21.6\n"
        "Адрес: matrix-hCsi.aternos.me:47280\n"
        "Для включения обратитесь к Итто."
    ),
    "инициалы": "🅼🆇 Если вы очень патриотичны, можете поставить инициал MX.",
}

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
                f"Добро пожаловать в Matrix, {member.first_name}! "
                "Надеюсь, вам здесь понравится и вы приживетесь🩷\n\n"
                "Если у вас возникнут трудности или вопросы, в любой момент "
                "вы можете обратиться к нашей администрации, она рада вам помочь.\n\n"
                "Несколько вопросов для знакомства:\n"
                "– Как к вам обращаться?\n"
                "– Какие у вас увлечения?\n"
                "– Как проходит день?\n\n"
                "В чате существуют автоматические ответы, список: "
                "норма, дискорд, инициалы, майнкрафт, рест."
            )
            await update.message.reply_text(text)

# --- 2. Триггеры в Группе 1 ---
async def triggers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_1_ID or not update.message.text:
        return
    text = update.message.text.lower()
    for key, answer in TRIGGERS.items():
        if key in text:
            await update.message.reply_text(answer)
            break

# --- 3. Приветствие в ЛС по /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Доброго времени суток! Здесь вы можете оставить заявку или жалобу."
    )

# --- 4. Пересылка ЛС в Группу 2 + подтверждение ---
async def forward_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message.text:
        return

    user = update.effective_user
    msg = f"📩 от {user.full_name} (@{user.username}):\n\n{update.message.text}"
    try:
        await context.bot.send_message(chat_id=GROUP_2_ID, text=msg)
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")

    await update.message.reply_text("Ваше сообщение дошло до администраторов!")

# --- Запуск бота в фоне ---
def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Chat(GROUP_1_ID),
            triggers,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            forward_dm,
        )
    )
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
