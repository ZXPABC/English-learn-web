"""FastAPI 入口:创建应用、挂载静态文件、注册所有路由"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SECRET_KEY
from .database import Base, engine
from .dependencies import BASE_DIR
from .listening_data import load as load_listening_data
from .quiz_data import load as load_quiz_data
from .routers import admin, admin_api, api, auth, pages
from .seed import seed_if_empty
from .word_lookup import load as load_word_lookup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时:自动建表、写入示例数据(数据库为空时才写入)、加载题库和查词索引"""
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    load_quiz_data()
    load_listening_data()
    load_word_lookup()
    yield


app = FastAPI(
    title="轻松学英语",
    description="一个简单的英语学习网站",
    lifespan=lifespan,
)

# 登录会话(管理员 + 学生共用):基于签名 Cookie,不需要额外的服务
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 静态文件(CSS / JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 学生端:注册/登录 + 页面 + 接口
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(api.router)
# 后台管理:页面 + 接口
app.include_router(admin.router)
app.include_router(admin_api.router)
