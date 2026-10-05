"""学生端页面路由(返回 HTML 页面,全部需要登录)"""
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import templates
from ..listening_data import total as listening_total
from ..models import Lesson, User, Word
from ..quiz_data import total as quiz_total
from ..task_words import DICTIONARIES, label
from .auth import current_user, login_wall

router = APIRouter()


def guard(request: Request, db: Session) -> User | RedirectResponse:
    """登录墙:未登录或被禁用返回跳转登录页的响应,正常返回当前用户"""
    user = current_user(request, db)
    if user is None or not user.is_active:
        return login_wall(request, user)
    return user


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    """首页:统计概览"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    word_count = db.scalar(select(func.count(Word.id)))
    lesson_count = db.scalar(select(func.count(Lesson.id)))
    category_count = len(db.scalars(select(Word.category).distinct()).all())
    return templates.TemplateResponse(request, "index.html", {
        "user": user,
        "word_count": word_count,
        "lesson_count": lesson_count,
        "category_count": category_count,
        "quiz_total": quiz_total(),
        "listening_total": listening_total(),
        "active": "index",
    })


@router.get("/words", response_class=HTMLResponse)
def words_page(request: Request, db: Session = Depends(get_db)):
    """单词学习页(单词数据由 /api/words 接口提供)"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(request, "words.html", {"user": user, "active": "words"})


@router.get("/quiz", response_class=HTMLResponse)
def quiz_page(request: Request, db: Session = Depends(get_db)):
    """句子测验页"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(request, "quiz.html", {"user": user, "active": "quiz"})


@router.get("/listening", response_class=HTMLResponse)
def listening_page(request: Request, db: Session = Depends(get_db)):
    """听力训练页"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(request, "listening.html", {"user": user, "active": "listening"})


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request, db: Session = Depends(get_db), dict_key: str = Query("gaokao", alias="dict")):
    """单词任务总览页(进度按账号保存在服务器上)"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    if dict_key not in DICTIONARIES:
        return templates.TemplateResponse(request, "404.html", {"user": user, "active": "tasks"}, status_code=404)
    return templates.TemplateResponse(request, "tasks.html", {
        "user": user,
        "active": "tasks",
        "dict_key": dict_key,
        "dict_label": label(dict_key),
    })


@router.get("/tasks/{dict_key}/{group_no}", response_class=HTMLResponse)
def task_group_page(request: Request, dict_key: str, group_no: int, db: Session = Depends(get_db)):
    """某本词库某一组的学习页"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    if dict_key not in DICTIONARIES:
        return templates.TemplateResponse(request, "404.html", {"user": user, "active": "tasks"}, status_code=404)
    return templates.TemplateResponse(request, "task_group.html", {
        "user": user,
        "active": "tasks",
        "dict_key": dict_key,
        "dict_label": label(dict_key),
        "group": group_no,
    })


@router.get("/tasks/{group_no}", response_class=HTMLResponse)
def task_group_legacy(request: Request, group_no: int):
    """兼容旧地址:/tasks/5 自动转到 /tasks/gaokao/5(纯跳转,登录墙由目标页负责)"""
    return RedirectResponse(f"/tasks/gaokao/{group_no}", status_code=308)


@router.get("/lessons", response_class=HTMLResponse)
def lessons_page(request: Request, db: Session = Depends(get_db)):
    """课程列表页"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    lessons = db.scalars(select(Lesson).order_by(Lesson.id)).all()
    return templates.TemplateResponse(request, "lessons.html", {"user": user, "lessons": lessons, "active": "lessons"})


@router.get("/lessons/{lesson_id}", response_class=HTMLResponse)
def lesson_detail(request: Request, lesson_id: int, db: Session = Depends(get_db)):
    """课程详情页"""
    user = guard(request, db)
    if isinstance(user, RedirectResponse):
        return user
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        return templates.TemplateResponse(request, "404.html", {"user": user, "active": ""}, status_code=404)
    return templates.TemplateResponse(request, "lesson_detail.html", {"user": user, "lesson": lesson, "active": "lessons"})
