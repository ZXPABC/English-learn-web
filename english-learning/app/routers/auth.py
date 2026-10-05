"""学生端注册/登录/退出

用户账号由学生在注册页自己创建,存进数据库,后台 /admin/users 统一管理。
会话沿用 SessionMiddleware 的签名 Cookie,学生会话用 "user_id" 键,
和管理员的 "admin_id" 互不干扰。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import templates
from ..models import User
from ..security import hash_password, verify_password

router = APIRouter()


def current_user(request: Request, db: Session) -> User | None:
    """从会话取出当前学生用户,未登录返回 None"""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(User, user_id)


def login_wall(request: Request, user: User | None) -> RedirectResponse | None:
    """学生页面的登录墙:未登录或账号被禁用时返回跳转登录页的响应,正常返回 None

    禁用账号顺带清掉会话,让"禁用"立即生效(不用等 Cookie 过期)。
    """
    if user is None:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    if not user.is_active:
        request.session.pop("user_id", None)
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    return None


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """API 专用鉴权:未登录或已禁用直接返回 401"""
    user = current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已被禁用,请联系管理员")
    return user


def safe_next(next_url: str) -> str:
    """防开放重定向:只允许站内以 / 开头的路径,否则回首页"""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next_url: str = Query("", alias="next")):
    """登录页"""
    return templates.TemplateResponse(request, "login.html", {
        "error": None, "next": safe_next(next_url), "active": "",
    })


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          next_url: str = Form("", alias="next"), db: Session = Depends(get_db)):
    """处理登录表单:成功后记录最近登录时间并跳回原页面"""
    user = db.scalar(select(User).where(User.username == username.strip()))
    # 先验密码再提示禁用,避免暴露账号是否存在
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {
            "error": "用户名或密码错误", "next": safe_next(next_url), "active": "",
        }, status_code=401)
    if not user.is_active:
        return templates.TemplateResponse(request, "login.html", {
            "error": "账号已被禁用,请联系管理员", "next": safe_next(next_url), "active": "",
        }, status_code=401)
    user.last_login = datetime.now()
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse(safe_next(next_url), status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, next_url: str = Query("", alias="next")):
    """注册页"""
    return templates.TemplateResponse(request, "register.html", {
        "error": None, "next": safe_next(next_url), "active": "",
    })


@router.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...),
             password2: str = Form(...), next_url: str = Form("", alias="next"),
             db: Session = Depends(get_db)):
    """处理注册表单:逐个校验,成功则自动登录"""
    error = None
    name = username.strip()
    if not (2 <= len(name) <= 20) or " " in name:
        error = "用户名需要 2-20 个字符,不能有空格"
    elif db.scalar(select(User).where(User.username == name)) is not None:
        error = "用户名已被注册,换一个试试"
    elif len(password) < 6:
        error = "密码至少需要 6 位"
    elif password != password2:
        error = "两次输入的密码不一致"
    if error is not None:
        return templates.TemplateResponse(request, "register.html", {
            "error": error, "next": safe_next(next_url), "active": "",
        }, status_code=400)

    user = User(username=name, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse(safe_next(next_url), status_code=303)


@router.get("/logout")
def logout(request: Request):
    """退出登录:只清学生的会话键,不影响同一浏览器里的管理员登录"""
    request.session.pop("user_id", None)
    return RedirectResponse("/login", status_code=303)
