"""数据库连接"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# check_same_thread=False 是 SQLite 配合 FastAPI 多线程的标准写法
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """所有数据表模型都继承这个类"""
    pass


def get_db():
    """FastAPI 依赖:每个请求拿到一个数据库会话,请求结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
