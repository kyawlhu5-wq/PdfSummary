from datetime import datetime, timedelta, timezone
import io
import os
import sqlite3
from flask import Flask, jsonify, request
import google.generativeai as genai
from pypdf import PdfReader
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
try:
  ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "8775300748"))
except:
  ADMIN_TELEGRAM_ID = 8775300748

# Safe Gemini configuration
try:
  if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    generation_model = genai.GenerativeModel("gemini-2.5-flash")
  else:
    generation_model = None
except Exception as e:
  print(f"Gemini Init Error: {e}")
  generation_model = None

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MM_TIMEZONE = timezone(timedelta(hours=6, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bot_database.db")


def get_mm_time():
  return datetime.now(MM_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def init_db():
  try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'pending',
                joined_at TEXT
            )
        """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_books (
                book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                book_content TEXT,
                uploaded_at TEXT
            )
        """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                active_book_id INTEGER
            )
        """)
    conn.commit()
    conn.close()
  except Exception as e:
    print(f"DB Error: {e}")


init_db()


@app.route("/", methods=["GET", "POST"])
def webhook():
  if request.method == "GET":
    return "🤖 Telegram Book Summary Bot is running and healthy on Railway!", 200

  try:
    data = request.get_json(silent=True, force=True)
    if not data:
      return jsonify({"status": "ok"})

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    if "message" in data:
      message = data["message"]
      chat_id = message["chat"]["id"]
      user_id = message["from"]["id"]
      username = message["from"].get("username", "Unknown")
      text = message.get("text", "")

      if user_id == ADMIN_TELEGRAM_ID:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, status, joined_at)"
            " VALUES (?, ?, 'approved', ?)",
            (user_id, username, get_mm_time()),
        )
      else:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, status, joined_at)"
            " VALUES (?, ?, 'pending', ?)",
            (user_id, username, get_mm_time()),
        )
      conn.commit()

      cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
      row = cursor.fetchone()
      user_status = row[0] if row else "pending"
      conn.close()

      if user_status == "banned":
        try:
          url = f"{TELEGRAM_API_URL}/sendMessage"
          requests.post(
              url,
              json={
                  "chat_id": chat_id,
                  "text": "❌ တောင်းပန်ပါတယ်၊ သင့်အကောင့်အား ပိတ်ပင်ထားပါသည်။",
              },
              timeout=5,
          )
        except:
          pass
        return jsonify({"status": "ok"})

      if user_status == "pending" and user_id != ADMIN_TELEGRAM_ID:
        try:
          url = f"{TELEGRAM_API_URL}/sendMessage"
          requests.post(
              url,
              json={
                  "chat_id": chat_id,
                  "text": (
                      "⏳ သင်၏ အကောင့်ကို Admin အတည်ပြုပေးရန် စောင့်ဆိုင်းနေဆဲဖြစ်ပါသည်။"
                  ),
              },
              timeout=5,
          )
          requests.post(
              url,
              json={
                  "chat_id": ADMIN_TELEGRAM_ID,
                  "text": (
                      f"🔔 User အသစ်: `{user_id}` (@{username})\nအတည်ပြုရန်"
                      f" `/approve {user_id}` ဟု ရိုက်ပါ။"
                  ),
              },
              timeout=5,
          )
        except:
          pass
        return jsonify({"status": "ok"})

      if text == "/start":
        try:
          url = f"{TELEGRAM_API_URL}/sendMessage"
          requests.post(
              url,
              json={
                  "chat_id": chat_id,
                  "text": (
                      "မင်္ဂလာပါ 📚 စာအုပ်အနှစ်ချုပ် Bot မှ ကြိုဆိုပါတယ်။"
                      " အနှစ်ချုပ်လိုသော PDF/TXT ဖိုင် တင်နိုင်ပါပြီ!"
                  ),
              },
              timeout=5,
          )
        except:
          pass

    return jsonify({"status": "ok"})
  except Exception as e:
    print(f"Webhook Error: {e}")
    return jsonify({"status": "error"}), 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
