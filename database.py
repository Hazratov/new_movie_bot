from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from config import AsyncSessionLocal
from models import Movie

async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Movie.metadata.create_all)

async def get_movie_by_code(code: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        return result.scalar_one_or_none()

async def add_movie(code: str, file_id: str, caption: str):
    async with AsyncSessionLocal() as session:
        movie = Movie(code=code, file_id=file_id, caption=caption)
        session.add(movie)
        await session.commit()

async def delete_movie(movie_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Movie).where(Movie.id == movie_id))
        await session.commit()
