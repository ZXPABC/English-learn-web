"""页面模板等公共资源"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

# 所有路由共用这个模板引擎实例
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
