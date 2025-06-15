import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import time

# === Загрузка .env переменных ===
load_dotenv()
API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Пример: https://forecast-zoyy.onrender.com

USE_WEBHOOK = bool(WEBHOOK_URL)
print(USE_WEBHOOK)

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__) if USE_WEBHOOK else None

# === Список городов ===
CITIES = ['Москва', 'Севастополь', 'Рига', 'Лос-Анджелес']

# === Получение погоды ===
def get_weather_report(city):
    output = f"=== {city} ===\n"

    # --- Текущая погода ---
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru"
    weather_resp = requests.get(weather_url).json()

    if 'main' in weather_resp:
        desc = weather_resp['weather'][0]['description'].capitalize()
        temp = weather_resp['main']['temp']
        timezone_offset = weather_resp.get('timezone', 0)
        local_time = datetime.utcnow() + timedelta(seconds=timezone_offset)
        output += f"Местное время: {local_time.strftime('%Y-%m-%d %H:%M')}\n"
        output += f"Сейчас: {desc}, {temp}°C\n"
    else:
        return f"{city}: ошибка погоды: {weather_resp.get('message', 'Нет данных')}"

    # --- Прогноз на завтра ---
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang=ru"
    forecast_resp = requests.get(forecast_url).json()

    if 'list' in forecast_resp:
        output += "Прогноз на завтра:\n"
        timezone_offset = forecast_resp.get('city', {}).get('timezone', timezone_offset)
        tomorrow_date = (datetime.utcnow() + timedelta(days=1)).date()

        found = False
        for entry in forecast_resp['list']:
            local_dt = datetime.utcfromtimestamp(entry['dt']) + timedelta(seconds=timezone_offset)
            if local_dt.date() == tomorrow_date:
                time = local_dt.strftime('%H:%M')
                desc = entry['weather'][0]['description'].capitalize()
                temp = entry['main']['temp']
                output += f"{time} — {desc}, {temp}°C\n"
                found = True

        if not found:
            output += "Нет данных на завтра.\n"
    else:
        output += "Ошибка прогноза: " + forecast_resp.get('message', 'Нет данных') + "\n"

    return output.strip()

# === Обработка команды /start или /weather ===
@bot.message_handler(commands=['start', 'weather'])
def send_weather(message):
    bot.send_message(message.chat.id, "Получаю данные, подождите...")
#    report = "\n\n".join(get_weather_report(city) for city in CITIES)
#    bot.send_message(message.chat.id, report)
    

    for city in CITIES:
        try:
            report = get_weather_report(city)
            bot.send_message(message.chat.id, report)
            time.sleep(1.2)  # <== пауза между отправками
        except Exception as e:
            print(f"Ошибка при отправке по {city}: {e}")

    
    

# === POLLING ===
if not USE_WEBHOOK:
    print("⚙️  Работает в режиме polling")
    bot.remove_webhook()
    bot.infinity_polling()

# === WEBHOOK ===
if USE_WEBHOOK:
    print(f"🌐 Работает через Webhook: {WEBHOOK_URL}")

    @app.route(f"/{BOT_TOKEN}", methods=['POST'])
    def webhook():
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200

    @app.route("/", methods=["GET"])
    def index():
        return "✅ Бот работает через Webhook", 200

    @app.before_request
    def setup_webhook():
        bot.remove_webhook()
        full_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        success = bot.set_webhook(url=full_url)
        if success:
            print(f"✅ Webhook установлен: {full_url}")
        else:
            print(f"❌ Ошибка установки Webhook! Попробуй вручную:\n"
                  f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={full_url}")

    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 5000))
        print(f"🚀 Flask запускается на порту: {port}")
        app.run(host="0.0.0.0", port=port)
