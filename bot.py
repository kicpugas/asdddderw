import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from config import TOKEN
from handlers import main_menu, combat

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

async def main():
    dp.include_router(main_menu.router)
    dp.include_router(combat.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())