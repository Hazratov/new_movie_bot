import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from config import TOKEN, engine
from database import init_db
from handlers import router  # Import router instead of dp

# Initialize bot and dispatcher
bot = Bot(TOKEN)
dp = Dispatcher()

# Include routers
dp.include_router(router)

async def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Initialize database
    await init_db(engine)

    # Start polling
    try:
        logging.info("Bot starting...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())