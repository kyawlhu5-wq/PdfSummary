import os
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
try:
  ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "8775300748"))
except:
  ADMIN_TELEGRAM_ID = 8775300748

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


@app.route("/", methods=["GET", "POST"])
def webhook():
  if request.method == "GET":
    return "🤖 Bot is running perfectly!", 200

  try:
    data = request.get_json(silent=True, force=True)
    if not data:
      return jsonify({"status": "ok"}), 200

    if "message" in data:
      message = data["message"]
      chat_id = message["chat"]["id"]
      text = message.get("text", "")

      if text == "/start":
        try:
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
              timeout=3,
          )
        except Exception as e:
          print(f"Telegram API Error: {e}")

    return jsonify({"status": "ok"}), 200
  except Exception as e:
    print(f"Webhook Error: {e}")
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
