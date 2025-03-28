from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from aiogram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = os.getenv("ADMIN_IDS")
ADMIN_IDS = set(map(int, ADMIN_IDS.split(","))) if ADMIN_IDS else set()
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TOKEN)
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
