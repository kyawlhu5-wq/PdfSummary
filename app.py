from datetime import datetime, timedelta, timezone
import io
import os
import sqlite3
import google.generativeai as genai
from pypdf import PdfReader
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Environment Variables Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
try:
  ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "8775300748"))
except:
  ADMIN_TELEGRAM_ID = 8775300748

if GEMINI_API_KEY:
  try:
    genai.configure(api_key=GEMINI_API_KEY)
    generation_model = genai.GenerativeModel("gemini-2.5-flash")
  except:
    generation_model = None
else:
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


def send_telegram_message(chat_id, text, reply_markup=None):
  try:
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
      payload["reply_markup"] = reply_markup
    requests.post(url, json=payload, timeout=10)
  except:
    pass


def extract_file_content(file_bytes, file_name):
  try:
    if file_name.lower().endswith(".pdf"):
      reader = PdfReader(io.BytesIO(file_bytes))
      text = ""
      for page in reader.pages:
        t = page.extract_text()
        if t:
          text += t + "\n"
      return (
          text.strip()
          if text.strip()
          else "PDF ဖိုင်ထဲမှ စာသား ထုတ်ယူ၍ မရပါ။"
      )
    else:
      return file_bytes.decode("utf-8", errors="ignore")
  except Exception as e:
    return f"ဖိုင်ဖတ်ရှုရာတွင် အမှားရှိသည်: {str(e)}"


@app.route("/", methods=["GET", "POST"])
def webhook():
  if request.method == "GET":
    return "🤖 Telegram Book Summary Bot is running on Railway!"

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

      if user_status == "banned":
        send_telegram_message(
            chat_id,
            "❌ တောင်းပန်ပါတယ်၊ သင့်အကောင့်အား Bot သုံးစွဲခွင့် ပိတ်ပင်ထားပါသည်။",
        )
        conn.close()
        return jsonify({"status": "ok"})

      if user_status == "pending" and user_id != ADMIN_TELEGRAM_ID:
        send_telegram_message(
            chat_id,
            "⏳ သင်၏ အကောင့်ကို Admin အတည်ပြုပေးရန် စောင့်ဆိုင်းနေဆဲဖြစ်ပါသည်။",
        )
        send_telegram_message(
            ADMIN_TELEGRAM_ID,
            f"🔔 **User အသစ် တောင်းဆိုမှု:**\n- User ID: `{user_id}`\n- Username:"
            f" @{username}\n- အချိန်: {get_mm_time()}\n\nအတည်ပြုရန် `/approve"
            f" {user_id}` ဟု ရိုက်ပါ။",
        )
        conn.close()
        return jsonify({"status": "ok"})

      if user_id == ADMIN_TELEGRAM_ID:
        if text.startswith("/approve "):
          target_id = text.split(" ")[1]
          cursor.execute(
              "UPDATE users SET status = 'approved' WHERE user_id = ?",
              (target_id,),
          )
          conn.commit()
          send_telegram_message(
              chat_id, f"✅ User ID `{target_id}` အား ခွင့်ပြုလိုက်ပါပြီ။"
          )
          send_telegram_message(
              int(target_id),
              "🎉 သင့်အကောင့်ကို အတည်ပြုပေးလိုက်ပါပြီ။ ယခု Bot ကို"
              " စတင်သုံးစွဲနိုင်ပါပြီ။ `/start` ဟု ပို့ပါ။",
          )
          conn.close()
          return jsonify({"status": "ok"})
        elif text.startswith("/kick "):
          target_id = text.split(" ")[1]
          cursor.execute(
              "UPDATE users SET status = 'banned' WHERE user_id = ?",
              (target_id,),
          )
          conn.commit()
          send_telegram_message(
              chat_id, f"🚫 User ID `{target_id}` အား ဖယ်ရှားပိတ်ပင်လိုက်ပါပြီ။"
          )
          conn.close()
          return jsonify({"status": "ok"})
        elif text == "/logs":
          cursor.execute(
              "SELECT user_id, username, status, joined_at FROM users"
          )
          users = cursor.fetchall()
          log_text = "📊 **User အဝင်အထွက် မှတ်တမ်း (မြန်မာစံတော်ချိန်):**\n\n"
          for u in users:
            log_text += (
                f"• ID: `{u[0]}` | @{u[1]} | Status: *{u[2]}* | 🕒 {u[3]}\n"
            )
          send_telegram_message(chat_id, log_text)
          conn.close()
          return jsonify({"status": "ok"})

      if text == "/start":
        send_telegram_message(
            chat_id,
            "မင်္ဂလာပါ 📚 **စာအုပ်အနှစ်ချုပ် Bot** မှ ကြိုဆိုပါတယ်။\n\nအနှစ်ချုပ်လိုသော"
            " PDF သို့မဟုတ် TXT စာအုပ်ဖိုင်များကို တင်ပို့နိုင်ပါသည်။",
        )
      elif "document" in message:
        file_id = message["document"]["file_id"]
        file_name = message["document"].get(
            "file_name", f"book_{get_mm_time()}.txt"
        )
        send_telegram_message(
            chat_id, "⏳ စာအုပ်ကို လက်ခံရရှိပါပြီ။ စာသားများ သိမ်းဆည်းနေပါပြီ..."
        )

        file_url = f"{TELEGRAM_API_URL}/getFile?file_id={file_id}"
        res = requests.get(file_url).json()
        if res.get("ok"):
          f_path = res["result"]["file_path"]
          dl_url = (
              f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{f_path}"
          )
          file_bytes = requests.get(dl_url).content
          book_content = extract_file_content(file_bytes, file_name)

          cursor.execute(
              "INSERT INTO user_books (user_id, file_name, book_content,"
              " uploaded_at) VALUES (?, ?, ?, ?)",
              (user_id, file_name, book_content, get_mm_time()),
          )
          book_id = cursor.lastrowid
          cursor.execute(
              "REPLACE INTO user_sessions (user_id, active_book_id) VALUES (?,"
              " ?)",
              (user_id, book_id),
          )
          conn.commit()

          send_telegram_message(
              chat_id,
              f"✅ **{file_name}** ကို သိမ်းဆည်းပြီးပါပြီ။ အနှစ်ချုပ်ရန် ရွေးချယ်ပါ -",
              reply_markup={
                  "inline_keyboard": [
                      [
                          {
                              "text": "📌 စာအုပ်တစ်အုပ်လုံး အနှစ်ချုပ်",
                              "callback_data": "summary_full",
                          }
                      ],
                      [
                          {
                              "text": "📖 အခန်းလိုက် အနှစ်ချုပ်",
                              "callback_data": "summary_chapters",
                          }
                      ],
                  ]
              },
          )

    elif "callback_query" in data:
      query = data["callback_query"]
      chat_id = query["message"]["chat"]["id"]
      user_id = query["from"]["id"]
      callback_data = query["data"]

      conn = sqlite3.connect(DB_PATH, check_same_thread=False)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT active_book_id FROM user_sessions WHERE user_id = ?",
          (user_id,),
      )
      session_row = cursor.fetchone()
      if not session_row:
        send_telegram_message(chat_id, "⚠️ ကျေးဇူးပြု၍ စာအုပ်တစ်အုပ် အရင်တင်ပါ။")
        conn.close()
        return jsonify({"status": "ok"})

      active_book_id = session_row[0]
      cursor.execute(
          "SELECT file_name, book_content FROM user_books WHERE book_id = ?",
          (active_book_id,),
      )
      book_row = cursor.fetchone()
      conn.close()

      if book_row and generation_model:
        file_name, book_content = book_row
        send_telegram_message(chat_id, "🔄 AI မှ အချက်အလက်များကို စီမံနေပါပြီ...")
        prompt = (
            f"ဤစာအုပ် ({file_name}) ၏ အဓိက အနှစ်သာရကို မြန်မာဘာသာဖြင့်"
            f" ခြုံငုံအနှစ်ချုပ်ပေးပါ:\n\n{book_content[:12000]}"
        )
        response = generation_model.generate_content(prompt)
        send_telegram_message(chat_id, response.text)

    return jsonify({"status": "ok"})
  except Exception as e:
    return jsonify({"status": "error"})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
