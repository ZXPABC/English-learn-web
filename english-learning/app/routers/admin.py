"""后台管理页面路由(返回 HTML)"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import templates
from ..models import Admin, Lesson, User, Word
from ..security import verify_password

router = APIRouter(prefix="/admin")


def get_admin(request: Request, db: Session) -> Admin | None:
    """从会话里取出当前登录的管理员,未登录返回 None"""
    admin_id = request.session.get("admin_id")
    if admin_id is None:
        return None
    return db.get(Admin, admin_id)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None):
    """登录页"""
    return templates.TemplateResponse(request, "admin/login.html", {"error": error})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    """处理登录表单"""
    admin = db.scalar(select(Admin).where(Admin.username == username))
    if admin is None or not verify_password(password, admin.password_hash):
        return templates.TemplateResponse(
            request, "admin/login.html", {"error": "用户名或密码错误"}, status_code=401)
    request.session["admin_id"] = admin.id
    return RedirectResponse("/admin", status_code=303)


@router.get("/logout")
def logout(request: Request):
    """退出登录"""
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """仪表盘:统计概览"""
    admin = get_admin(request, db)
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)

    stats = {
        "words": db.scalar(select(func.count(Word.id))),
        "lessons": db.scalar(select(func.count(Lesson.id))),
        "categories": len(db.scalars(select(Word.category).distinct()).all()),
        "users": db.scalar(select(func.count(User.id))),
    }
    # 各分类的单词数量(从多到少排列)
    category_rows = db.execute(
        select(Word.category, func.count(Word.id))
        .group_by(Word.category)
        .order_by(func.count(Word.id).desc())
    ).all()
    max_count = max((count for _, count in category_rows), default=0)
    recent_words = db.scalars(select(Word).order_by(Word.id.desc()).limit(5)).all()

    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "admin": admin,
        "stats": stats,
        "category_rows": category_rows,
        "max_count": max_count,
        "recent_words": recent_words,
        "active": "dashboard",
    })


@router.get("/words", response_class=HTMLResponse)
def words_page(request: Request, db: Session = Depends(get_db)):
    """单词管理页"""
    admin = get_admin(request, db)
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)
    categories = db.scalars(select(Word.category).distinct().order_by(Word.category)).all()
    return templates.TemplateResponse(request, "admin/words.html", {
        "admin": admin, "categories": categories, "active": "words",
    })


@router.get("/lessons", response_class=HTMLResponse)
def lessons_page(request: Request, db: Session = Depends(get_db)):
    """课程管理页"""
    admin = get_admin(request, db)
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "admin/lessons.html", {"admin": admin, "active": "lessons"})


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, db: Session = Depends(get_db)):
    """用户管理页:学生注册的账号在这里统一管理"""
    admin = get_admin(request, db)
    if admin is None:
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "admin/users.html", {"admin": admin, "active": "users"})
