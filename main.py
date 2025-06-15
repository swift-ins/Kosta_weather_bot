import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request
import telebot

# === Список городов ===
CITIES = ['Москва', 'Севастополь', 'Рига', 'Лос-Анджелес', 'Санкт-Петербург']


# === Загрузка .env переменных ===
load_dotenv()
API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

USE_WEBHOOK = bool(WEBHOOK_URL)  # Если есть URL — значит работаем через webhook

# === Инициализация бота ===
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__) if USE_WEBHOOK else None

# === Функция погоды ===
    
def get_weather_report0(city):
    output = f"=== {city} ===\n"

    # --- Текущая погода ---
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru"
    weather_resp = requests.get(weather_url).json()

    if 'main' in weather_resp:
        desc = weather_resp['weather'][0]['description'].capitalize()
        temp = weather_resp['main']['temp']
        
        # Местное время
        timezone_offset = weather_resp.get('timezone', 0)
        local_time = datetime.utcnow() + timedelta(seconds=timezone_offset)
        time_str = local_time.strftime('%Y-%m-%d %H:%M')

        output += f"Местное время: {time_str}\n"
        output += f"Сейчас: {desc}, {temp}°C\n"
    else:
        return f"{city}: ошибка погоды: {weather_resp.get('message', 'Нет данных')}"

    # --- Прогноз на завтра ---
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang=ru"
    forecast_resp = requests.get(forecast_url).json()

    if 'list' in forecast_resp:
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')

        output += "Прогноз на завтра:\n"
        found = False
        for entry in forecast_resp['list']:
            if entry['dt_txt'].startswith(tomorrow_str):
                time = entry['dt_txt'][11:16]
                desc = entry['weather'][0]['description'].capitalize()
                temp = entry['main']['temp']
                output += f"{time} — {desc}, {temp}°C\n"
                found = True

        if not found:
            output += "Нет данных на завтра.\n"
    else:
        output += "Ошибка прогноза: " + forecast_resp.get('message', 'Нет данных') + "\n"

    return output.strip()
    
    
def get_weather_report(city):
    output = f"=== {city} ===\n"

    # --- Текущая погода ---
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru"
    weather_resp = requests.get(weather_url).json()

    if 'main' in weather_resp:
        desc = weather_resp['weather'][0]['description'].capitalize()
        temp = weather_resp['main']['temp']
        
        # Местное время (по timezone из текущей погоды)
        timezone_offset = weather_resp.get('timezone', 0)
        local_time = datetime.utcnow() + timedelta(seconds=timezone_offset)
        time_str = local_time.strftime('%Y-%m-%d %H:%M')

        output += f"Местное время: {time_str}\n"
        output += f"Сейчас: {desc}, {temp}°C\n"
    else:
        return f"{city}: ошибка погоды: {weather_resp.get('message', 'Нет данных')}"

    # --- Прогноз на завтра ---
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric&lang=ru"
    forecast_resp = requests.get(forecast_url).json()

    if 'list' in forecast_resp:
        output += "Прогноз на завтра:\n"
        found = False

        # Получаем timezone из forecast (если не нашли ранее)
        timezone_offset = forecast_resp.get('city', {}).get('timezone', timezone_offset)

        # Целевая дата (только год-месяц-день)
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_date = tomorrow.date()

        for entry in forecast_resp['list']:
            utc_dt = datetime.utcfromtimestamp(entry['dt'])
            local_dt = utc_dt + timedelta(seconds=timezone_offset)

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
    report = ""
    for city in CITIES:
        report += get_weather_report(city) + "\n\n"

    bot.send_message(message.chat.id, report.strip())

# === POLLING режим ===

if not USE_WEBHOOK:
    print("⚙️  Работает в режиме polling")
#    bot.remove_webhook()  # <<< Важно!
    bot.infinity_polling()


# === WEBHOOK режим ===
if USE_WEBHOOK:
    print(f"🌐 Работает через Webhook: {WEBHOOK_URL}")

    @app.route(f"/{BOT_TOKEN}", methods=['POST'])
    def webhook():
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "OK", 200

    @app.route("/", methods=["GET"])
    def index():
        return "Бот работает", 200

    # Установка webhook при старте (если нужно)
    @app.before_request
    def set_webhook():
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
