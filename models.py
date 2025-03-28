from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, BigInteger

Base = declarative_base()

class Movie(Base):
    __tablename__ = "movies"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    file_id = Column(String, nullable=False)
    caption = Column(Text, nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)


class MandatoryChannel(Base):
    __tablename__ = "mandatory_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String, nullable=False)
    link = Column(String, nullable=False)