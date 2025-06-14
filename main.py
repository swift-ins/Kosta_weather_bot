import os
import telebot
import requests
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", '1f30db42752361354d4cf1f02835861e')

# Проверка обязательных переменных
if not BOT_TOKEN:
    logger.error("Не указан BOT_TOKEN в переменных окружения!")
    raise ValueError("Токен бота не найден")

# Создаем экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

# Кэш для хранения данных о погоде (упрощенный вариант)
weather_cache = {}
CACHE_EXPIRATION = timedelta(minutes=30)

def get_weather(city):
    """Получение текущей погоды с кэшированием"""
    cache_key = f"weather_{city}"
    if cache_key in weather_cache:
        cached_data = weather_cache[cache_key]
        if datetime.now() - cached_data['timestamp'] < CACHE_EXPIRATION:
            return cached_data['temperature']
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            temperature = data['main']['temp']
            weather_cache[cache_key] = {
                'temperature': temperature,
                'timestamp': datetime.now()
            }
            return temperature
        logger.warning(f"Ошибка при запросе погоды для {city}: {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {str(e)}")
    return None

def get_forecast(city):
    """Получение прогноза погоды на завтра"""
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            tomorrow = datetime.now() + timedelta(days=1)
            target_time = tomorrow.replace(hour=datetime.now().hour, minute=0, second=0, microsecond=0)
            
            for forecast in data['list']:
                forecast_time = datetime.strptime(forecast['dt_txt'], '%Y-%m-%d %H:%M:%S')
                if forecast_time.date() == target_time.date() and forecast_time.hour == target_time.hour:
                    return forecast['main']['temp']
        logger.warning(f"Ошибка при запросе прогноза для {city}: {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка при получении прогноза: {str(e)}")
    return None

def get_local_time(city_timezone):
    """Получение локального времени с обработкой ошибок"""
    try:
        timezone = pytz.timezone(city_timezone)
        return datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Ошибка получения времени для {city_timezone}: {str(e)}")
        return "недоступно"

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    bot.reply_to(message, 
        "Привет! Я могу показать текущее время, температуру и прогноз погоды в разных городах. "
        "Напишите /w для получения информации или /help для справки.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Обработчик команды /help"""
    bot.reply_to(message,
        "Доступные команды:\n"
        "/start - начать работу с ботом\n"
        "/w - получить информацию о погоде и времени\n"
        "/help - показать эту справку")

@bot.message_handler(commands=['w'])
def weather(message):
    """Обработчик команды /w - основная логика бота"""
    try:
        # Получаем и форматируем данные
        cities = [
            ('Москва', 'Europe/Moscow'),
            ('Рига', 'Europe/Riga'),
            ('Севастополь', 'Europe/Simferopol')
        ]
        
        weather_data = []
        forecast_data = []
        
        for city, timezone in cities:
            # Время
            current_time = get_local_time(timezone)
            
            # Текущая погода
            temp = get_weather(city)
            temp_text = f"{temp}°C" if temp is not None else "недоступно"
            weather_data.append(f"  - {city}: {current_time}, {temp_text}")
            
            # Прогноз
            forecast = get_forecast(city)
            if forecast is not None:
                forecast_data.append(f"  - {city}: {forecast}°C")
        
        # Формируем ответ
        response = (
            "⏰ Текущее время и температура:\n" +
            "\n".join(weather_data) +
            "\n\n🌤 Прогноз на завтра:\n" +
            ("\n".join(forecast_data) if forecast_data else "данные недоступны"))
        
        bot.send_message(message.chat.id, response)
    except Exception as e:
        logger.error(f"Ошибка в обработчике weather: {str(e)}")
        bot.send_message(message.chat.id, "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.")

# Альтернативный запуск для Render
def run_webhook():
    from flask import Flask, request
    app = Flask(__name__)
    
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL не указан, используется polling")
        return bot.polling()
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return ''
        return 'Bad request', 400
    
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    logger.info("Запуск бота...")
    # Автоматическое определение способа запуска
    if os.getenv('RENDER'):
        run_webhook()
    else:
        bot.polling()