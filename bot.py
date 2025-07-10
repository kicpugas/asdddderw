import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from config import TOKEN
from handlers import main_menu, combat

# Укажи свой адрес Render здесь!
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = "https://asdddderw.onrender.com/webhook"  # ← заменишь после деплоя

# Создание бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Подключение роутеров
dp.include_router(main_menu.router)
dp.include_router(combat.router)

# Обработка вебхука
async def handle_webhook(request: web.Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return web.Response()

# Создание aiohttp-приложения
async def create_app():
    app = web.Application()

    async def on_startup(app):
        await bot.set_webhook(WEBHOOK_URL)

    async def on_shutdown(app):
        await bot.delete_webhook()
        await bot.session.close()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_post(WEBHOOK_PATH, handle_webhook)

    return app
