import asyncio
import threading
import logging
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from analyzer import analyze

BOT_TOKEN = "8945571583:AAEhedUwZ240ed7sHjHKKllPHEleV7Adkms"

logging.basicConfig(level=logging.WARNING)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне текст или файл (.txt / .docx) — "
        "я проверю его на ИИ-контент, заимствования и оригинальность.\n\n"
        "Минимум 50 символов, максимум 10 000."
    )


def format_result(d: dict) -> str:
    verdict_ai = (
        "✅ Человек" if d["ai"] < 30
        else ("⚠️ Смешанный" if d["ai"] < 60 else "🤖 ИИ")
    )

    lines = [
        "📊 *Результат проверки*\n",
        f"✦ Оригинальность:  *{d['originality']}%*",
        f"⇄ Заимствование:   *{d['borrowing']}%*",
        f"❝ Цитирование:     *{d['citation']}%*",
        f"⚡ ИИ-контент:     *{d['ai']}%*  {verdict_ai}",
        "",
        "📝 *Статистика*",
        f"Слов: {d['stats']['words']} | Предложений: {d['stats']['sentences']} | Уникальных: {d['stats']['unique_words']}",
        f"Средняя длина предложения: {d['stats']['avg_sent_len']} слов",
    ]

    if d["details"]["ai_phrases"]:
        phrases = ", ".join(f'«{p}»' for p in d["details"]["ai_phrases"][:3])
        lines += ["", f"🔍 *Маркеры ИИ:* {phrases}"]

    if d["details"]["borrow_phrases"]:
        phrases = ", ".join(f'«{p}»' for p in d["details"]["borrow_phrases"][:3])
        lines += [f"📚 *Маркеры заимствований:* {phrases}"]

    return "\n".join(lines)


async def process_text(update: Update, text: str):
    if len(text) < 50:
        await update.message.reply_text("Текст слишком короткий. Нужно минимум 50 символов.")
        return
    if len(text) > 10000:
        await update.message.reply_text("Текст слишком длинный. Максимум 10 000 символов.")
        return

    msg = await update.message.reply_text("⏳ Анализирую...")
    d = analyze(text)
    await msg.edit_text(format_result(d), parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_text(update, update.message.text.strip())


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    name = doc.file_name or ""

    if not (name.endswith(".txt") or name.endswith(".docx")):
        await update.message.reply_text("Поддерживаются только файлы .txt и .docx")
        return

    msg = await update.message.reply_text("📂 Читаю файл...")

    file = await doc.get_file()
    buf = io.BytesIO()
    await file.download_to_memory(buf)
    buf.seek(0)

    try:
        if name.endswith(".txt"):
            text = buf.read().decode("utf-8", errors="ignore")
        else:
            from docx import Document
            document = Document(buf)
            text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    except Exception as e:
        await msg.edit_text(f"Не удалось прочитать файл: {e}")
        return

    text = text.strip()
    if len(text) < 50:
        await msg.edit_text("Файл слишком короткий или пустой (минимум 50 символов).")
        return
    if len(text) > 10000:
        text = text[:10000]

    await msg.edit_text("⏳ Анализирую...")
    d = analyze(text)
    await msg.edit_text(format_result(d), parse_mode="Markdown")


def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    loop.run_until_complete(app.run_polling(drop_pending_updates=True))


def start_bot_thread():
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
