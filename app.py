import logging
import os
import threading
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
from decoder.core import analyze_code, beautify_code, basic_decode, safe_filename

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("html-decode-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_MB", "5")) * 1024 * 1024
PORT = int(os.getenv("PORT", "10000"))

app = Flask(__name__)
telegram_app = None


@app.get("/")
def home():
    return jsonify({
        "service": "HTML Decode Telegram Bot",
        "status": "running",
        "note": "Send an HTML/JS/TXT file to the Telegram bot to analyze it."
    })


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


def help_text():
    return (
        "🧰 HTML Decode Bot\n\n"
        "একটি .html, .htm, .js অথবা .txt ফাইল পাঠাও।\n\n"
        "কমান্ড:\n"
        "/analyze — পরের ফাইল বিশ্লেষণ\n"
        "/beautify — পরের ফাইল format/clean\n"
        "/decode — নিরাপদ basic decode চেষ্টা\n"
        "/help — সাহায্য\n\n"
        "ফাইল পাঠানোর আগে কমান্ড বেছে নাও, অথবা ফাইলের caption-এ "
        "/analyze, /beautify বা /decode লিখো।\n\n"
        "⚠️ এটি কোড execute করে না। সব obfuscation পুরোপুরি reverse করা সম্ভব নয়।"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "analyze"
    await update.effective_message.reply_text(
        "স্বাগতম! HTML/JavaScript ফাইল পাঠাও।\n\n" + help_text()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(help_text())


async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    context.user_data["mode"] = mode
    labels = {
        "analyze": "বিশ্লেষণ",
        "beautify": "Beautify / Format",
        "decode": "Basic Decode",
    }
    await update.effective_message.reply_text(
        f"পরের HTML/JS/TXT ফাইলের জন্য মোড: {labels[mode]}। এখন ফাইল পাঠাও।"
    )


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "analyze")


async def beautify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "beautify")


async def decode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_mode(update, context, "decode")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    doc = message.document
    if not doc:
        return

    filename = safe_filename(doc.file_name or "uploaded_code.txt")
    allowed = filename.lower().endswith((".html", ".htm", ".js", ".txt", ".mjs", ".cjs"))
    if not allowed:
        await message.reply_text("এই ফাইল টাইপ সমর্থিত নয়। .html, .htm, .js বা .txt ফাইল পাঠাও।")
        return

    if doc.file_size and doc.file_size > MAX_FILE_BYTES:
        await message.reply_text(
            f"ফাইলটি বড়। সর্বোচ্চ অনুমোদিত সাইজ {MAX_FILE_BYTES // (1024 * 1024)} MB।"
        )
        return

    mode = context.user_data.get("mode", "analyze")
    caption = (message.caption or "").lower()
    for candidate in ("analyze", "beautify", "decode"):
        if f"/{candidate}" in caption:
            mode = candidate
            break

    status = await message.reply_text("ফাইল পড়ছি এবং নিরাপদভাবে বিশ্লেষণ করছি…")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        raw = await tg_file.download_as_bytearray()
        if len(raw) > MAX_FILE_BYTES:
            await status.edit_text("ফাইলটি নির্ধারিত সাইজের চেয়ে বড়।")
            return
        source = bytes(raw).decode("utf-8", errors="replace")

        if mode == "beautify":
            output = beautify_code(source)
            report = "✅ Beautify/format সম্পন্ন। এটি formatting, সম্পূর্ণ deobfuscation নয়।"
            out_name = safe_filename(filename.rsplit(".", 1)[0] + "_beautified." + filename.rsplit(".", 1)[-1])
        elif mode == "decode":
            output, notes = basic_decode(source)
            report = "🔎 Basic decode সম্পন্ন।\n" + "\n".join(f"• {n}" for n in notes[:8])
            out_name = safe_filename(filename.rsplit(".", 1)[0] + "_decoded." + filename.rsplit(".", 1)[-1])
        else:
            report = analyze_code(source)
            output = ""
            out_name = ""

        await status.delete()
        # Telegram messages have a practical size limit; split the report safely.
        if mode == "analyze":
            for start_idx in range(0, len(report), 3800):
                await message.reply_text(report[start_idx:start_idx + 3800])
        else:
            await message.reply_text(report)
            if not output.strip():
                await message.reply_text("কোনো output তৈরি হয়নি।")
                return
            encoded = output.encode("utf-8")
            if len(encoded) > 45 * 1024 * 1024:
                await message.reply_text("Output অনেক বড়; Telegram-এ পাঠানো যাচ্ছে না।")
                return
            from io import BytesIO
            bio = BytesIO(encoded)
            bio.name = out_name
            await message.reply_document(
                document=bio,
                filename=out_name,
                caption="তৈরি করা ফাইল। ব্যবহারের আগে কোড নিজে review করো; আমি এটি execute করিনি।",
            )
    except Exception:
        logger.exception("Processing failed")
        try:
            await status.edit_text("ফাইল প্রসেস করা যায়নি। ফাইলটি valid UTF-8 text কি না পরীক্ষা করো।")
        except Exception:
            await message.reply_text("ফাইল প্রসেস করা যায়নি। অন্য একটি ছোট HTML/JS/TXT ফাইল চেষ্টা করো।")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg and msg.text and not msg.text.startswith("/"):
        await msg.reply_text("একটি .html, .htm, .js বা .txt ফাইল document হিসেবে পাঠাও। /help লিখলে নির্দেশনা পাবে।")


def run_flask():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)


def main():
    global telegram_app
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("analyze", analyze_cmd))
    telegram_app.add_handler(CommandHandler("beautify", beautify_cmd))
    telegram_app.add_handler(CommandHandler("decode", decode_cmd))
    telegram_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("Starting Telegram polling bot and health web server")
    telegram_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
