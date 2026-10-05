"""后台管理 API(增删改查,所有接口都需要管理员登录)"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Admin, Lesson, ListeningRecord, QuizDraft, QuizRecord, User, UserProgress, Word
from ..schemas import (
    LessonCreate, LessonOut, LessonUpdate,
    ResetPassword, UserOut,
    WordCreate, WordOut, WordUpdate,
)
from ..security import hash_password

router = APIRouter(prefix="/admin/api")


def require_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    """API 专用鉴权:未登录直接返回 401"""
    admin_id = request.session.get("admin_id")
    if admin_id is None:
        raise HTTPException(status_code=401, detail="请先登录后台")
    admin = db.get(Admin, admin_id)
    if admin is None:
        raise HTTPException(status_code=401, detail="请先登录后台")
    return admin


# ---------- 单词管理 ----------

@router.get("/words", response_model=list[WordOut])
def list_words(search: str | None = None, category: str | None = None,
               db: Session = Depends(get_db), _admin: Admin = Depends(require_admin)):
    """单词列表,支持搜索(英文/中文)和分类筛选"""
    stmt = select(Word).order_by(Word.id.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Word.english.like(like) | Word.chinese.like(like))
    if category and category != "全部":
        stmt = stmt.where(Word.category == category)
    return db.scalars(stmt).all()


@router.post("/words", response_model=WordOut, status_code=201)
def create_word(payload: WordCreate, db: Session = Depends(get_db),
                _admin: Admin = Depends(require_admin)):
    """添加单词"""
    word = Word(**payload.model_dump())
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@router.put("/words/{word_id}", response_model=WordOut)
def update_word(word_id: int, payload: WordUpdate, db: Session = Depends(get_db),
                _admin: Admin = Depends(require_admin)):
    """修改单词(只更新传过来的字段)"""
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="单词不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(word, key, value)
    db.commit()
    db.refresh(word)
    return word


@router.delete("/words/{word_id}", status_code=204)
def delete_word(word_id: int, db: Session = Depends(get_db),
                _admin: Admin = Depends(require_admin)):
    """删除单词"""
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="单词不存在")
    db.delete(word)
    db.commit()
    return Response(status_code=204)


# ---------- 课程管理 ----------

@router.get("/lessons", response_model=list[LessonOut])
def list_lessons(db: Session = Depends(get_db), _admin: Admin = Depends(require_admin)):
    """课程列表"""
    return db.scalars(select(Lesson).order_by(Lesson.id)).all()


@router.post("/lessons", response_model=LessonOut, status_code=201)
def create_lesson(payload: LessonCreate, db: Session = Depends(get_db),
                  _admin: Admin = Depends(require_admin)):
    """添加课程"""
    lesson = Lesson(**payload.model_dump())
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.put("/lessons/{lesson_id}", response_model=LessonOut)
def update_lesson(lesson_id: int, payload: LessonUpdate, db: Session = Depends(get_db),
                  _admin: Admin = Depends(require_admin)):
    """修改课程"""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int, db: Session = Depends(get_db),
                  _admin: Admin = Depends(require_admin)):
    """删除课程"""
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    db.delete(lesson)
    db.commit()
    return Response(status_code=204)


# ---------- 用户管理 ----------

def user_dict(user: User, counts: dict[int, int]) -> UserOut:
    """把用户对象转成接口返回格式,附上已掌握单词数"""
    return UserOut(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        last_login=user.last_login,
        is_active=user.is_active,
        mastered_count=counts.get(user.id, 0),
    )


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: Admin = Depends(require_admin)):
    """全部注册用户(附每人已掌握单词总数)"""
    users = db.scalars(select(User).order_by(User.id)).all()
    counts: dict[int, int] = {}
    for user_id, indices_json in db.execute(
            select(UserProgress.user_id, UserProgress.indices_json)).all():
        counts[user_id] = counts.get(user_id, 0) + len(json.loads(indices_json or "[]"))
    return [user_dict(u, counts) for u in users]


@router.post("/users/{user_id}/toggle-active", status_code=204)
def toggle_user(user_id: int, db: Session = Depends(get_db), _admin: Admin = Depends(require_admin)):
    """禁用/启用账号(禁用后该用户下一次请求就会被踢下线)"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return Response(status_code=204)


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_user_password(user_id: int, payload: ResetPassword, db: Session = Depends(get_db),
                        _admin: Admin = Depends(require_admin)):
    """重置用户密码"""
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return Response(status_code=204)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _admin: Admin = Depends(require_admin)):
    """删除用户,并先删掉他的学习进度、测验成绩、测验草稿和听力成绩(SQLite 没开外键,要手动删)"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.execute(delete(UserProgress).where(UserProgress.user_id == user_id))
    db.execute(delete(QuizRecord).where(QuizRecord.user_id == user_id))
    db.execute(delete(QuizDraft).where(QuizDraft.user_id == user_id))
    db.execute(delete(ListeningRecord).where(ListeningRecord.user_id == user_id))
    db.delete(user)
    db.commit()
    return Response(status_code=204)
