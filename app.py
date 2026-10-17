from datetime import datetime, timedelta, timezone
import os
import sqlite3
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
try:
  ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "8775300748"))
except:
  ADMIN_TELEGRAM_ID = 8775300748

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
MM_TIMEZONE = timezone(timedelta(hours=6, minutes=30))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bot_database.db")


def init_db():
  try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'approved',
                joined_at TEXT
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
    return "🤖 Bot is running perfectly!", 200

  try:
    data = request.get_json(silent=True, force=True)
    if not data:
      return jsonify({"status": "ok"})

    if "message" in data:
      message = data["message"]
      chat_id = message["chat"]["id"]
      text = message.get("text", "")

      if text == "/start":
        url = f"{TELEGRAM_API_URL}/sendMessage"
        requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": (
                    "မင်္ဂလာပါ 📚 စာအုပ်အနှစ်ချုပ် Bot မှ ကြိုဆိုပါတယ်။ ဆာဗာ"
                    " အောင်မြင်စွာ ချိတ်ဆက်ပြီးပါပြီ!"
                ),
            },
            timeout=5,
        )

    return jsonify({"status": "ok"})
  except Exception as e:
    return jsonify({"status": "ok"})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
