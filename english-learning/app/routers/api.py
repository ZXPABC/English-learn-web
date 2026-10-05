"""学生端 API 接口(返回 JSON 数据,供前端 JS 调用)"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ListeningRecord, QuizDraft, QuizRecord, User, UserProgress, Word
from .. import listening_data, quiz_data, word_lookup as word_index
from ..schemas import (ListeningProgressPut, ProgressPut, QuizAnswer, QuizDraftPut,
                       QuizProgressPut, QuizQuestion, QuizResult, WordOut)
from ..task_words import GROUP_SIZE, DICTIONARIES, dictionaries, get_group, group_count, label, total as task_total
from .auth import require_user

router = APIRouter(prefix="/api")


@router.get("/words", response_model=list[WordOut])
def list_words(category: str | None = None, db: Session = Depends(get_db)):
    """单词列表,可按分类筛选"""
    stmt = select(Word).order_by(Word.id)
    if category and category != "全部":
        stmt = stmt.where(Word.category == category)
    return db.scalars(stmt).all()


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """所有单词分类"""
    return list(db.scalars(select(Word.category).distinct().order_by(Word.category)))


# ---------- 句子测验(看英文句子选中文,题库在 app/data/quiz_sentences.json) ----------

@router.get("/quiz/groups")
def quiz_groups():
    """测验题库概况:题目总数、每组数量、分组数"""
    return {
        "total": quiz_data.total(),
        "group_size": quiz_data.GROUP_SIZE,
        "groups": quiz_data.group_count(),
    }


@router.get("/quiz/question", response_model=QuizQuestion)
def quiz_question(group: int = 0):
    """随机出一题:一个英文句子 + 4 个中文选项(group=0 表示全部随机)"""
    q = quiz_data.make_question(group)
    if not q:
        raise HTTPException(status_code=400, detail="这个分组不存在,请重新选择")
    return q


@router.get("/quiz/group-questions", response_model=list[QuizQuestion])
def quiz_group_questions(group: int):
    """某一组的全部题目(顺序打乱),选组测验时一次取回、一轮做完一整组"""
    qs = quiz_data.group_questions(group)
    if not qs:
        raise HTTPException(status_code=404, detail="这个分组不存在,请重新选择")
    return qs


# ---------- 测验成绩(按账号保存,做完一组即标记该组已完成) ----------

@router.get("/quiz/progress")
def get_quiz_progress(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """当前用户已完成的测验组:{组号: {score, total, finished_at}}"""
    rows = db.scalars(select(QuizRecord).where(QuizRecord.user_id == user.id)).all()
    return {
        "records": {
            str(r.group_no): {
                "score": r.score,
                "total": r.total,
                "finished_at": r.finished_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        }
    }


@router.post("/quiz/progress")
def put_quiz_progress(payload: QuizProgressPut, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """保存一组测验的成绩;做完一轮即标记该组已完成(再测一次会覆盖成最近一次成绩)"""
    if payload.group_no < 1 or payload.group_no > quiz_data.group_count():
        raise HTTPException(status_code=404, detail="这个分组不存在")
    row = db.scalar(select(QuizRecord).where(
        QuizRecord.user_id == user.id, QuizRecord.group_no == payload.group_no))
    if row is None:
        row = QuizRecord(user_id=user.id, group_no=payload.group_no)
        db.add(row)
    row.score = payload.score
    row.total = payload.total
    row.finished_at = datetime.now()
    db.commit()
    return {"group_no": row.group_no, "score": row.score, "total": row.total}


# ---------- 测验草稿(中途退出保存进度,下次接着做) ----------

def _draft_info(draft: dict) -> dict:
    """从草稿里取出给选组页用的摘要信息(做到第几题/得分/总题数)"""
    return {
        "next_index": draft.get("next_index", 1),
        "score": draft.get("score", 0),
        "total": len(draft.get("questions") or []),
    }


@router.get("/quiz/drafts")
def get_quiz_drafts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """当前用户所有进行中的测验草稿:{组号: 摘要}(选组页用来标黄色"进行中")"""
    rows = db.scalars(select(QuizDraft).where(QuizDraft.user_id == user.id)).all()
    return {"drafts": {str(r.group_no): _draft_info(json.loads(r.draft_json or "{}")) for r in rows}}


@router.get("/quiz/draft")
def get_quiz_draft(group: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """某一组的完整草稿(开始测验时用来恢复);没有草稿返回 404"""
    row = db.scalar(select(QuizDraft).where(
        QuizDraft.user_id == user.id, QuizDraft.group_no == group))
    if row is None:
        raise HTTPException(status_code=404, detail="这一组没有未做完的记录")
    return {"draft": json.loads(row.draft_json or "{}")}


@router.put("/quiz/draft")
def put_quiz_draft(payload: QuizDraftPut, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """保存(或覆盖)某一组的测验草稿:题目列表 + 做到第几题 + 得分 + 错题"""
    if payload.group_no < 1 or payload.group_no > quiz_data.group_count():
        raise HTTPException(status_code=404, detail="这个分组不存在")
    row = db.scalar(select(QuizDraft).where(
        QuizDraft.user_id == user.id, QuizDraft.group_no == payload.group_no))
    if row is None:
        row = QuizDraft(user_id=user.id, group_no=payload.group_no)
        db.add(row)
    row.draft_json = json.dumps(payload.draft)
    row.updated_at = datetime.now()
    db.commit()
    return {"group_no": row.group_no}


@router.delete("/quiz/draft")
def delete_quiz_draft(group: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """做完一整组后清掉草稿(该组从"进行中"变成"已完成")"""
    row = db.scalar(select(QuizDraft).where(
        QuizDraft.user_id == user.id, QuizDraft.group_no == group))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"deleted": True}


# ---------- 听力训练(听英文句子选中文,题库在 app/data/listening_sentences.json) ----------

@router.get("/listening/groups")
def listening_groups():
    """听力题库概况:题目总数、每组数量、分组数"""
    return {
        "total": listening_data.total(),
        "group_size": listening_data.GROUP_SIZE,
        "groups": listening_data.group_count(),
    }


@router.get("/listening/question", response_model=QuizQuestion)
def listening_question(group: int = 0):
    """随机出一题:一个英文句子 + 4 个中文选项(group=0 表示全部随机)

    前端只播放读音、不显示英文,答完才展示原文,所以判分在前端本地做。
    """
    q = listening_data.make_question(group)
    if not q:
        raise HTTPException(status_code=400, detail="这个分组不存在,请重新选择")
    return q


@router.get("/listening/group-questions", response_model=list[QuizQuestion])
def listening_group_questions(group: int):
    """某一组的全部题目(顺序打乱),选组训练时一次取回、一轮做完一整组"""
    qs = listening_data.group_questions(group)
    if not qs:
        raise HTTPException(status_code=404, detail="这个分组不存在,请重新选择")
    return qs


@router.get("/listening/progress")
def get_listening_progress(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """当前用户已完成的听力组:{组号: {score, total, finished_at}}"""
    rows = db.scalars(select(ListeningRecord).where(ListeningRecord.user_id == user.id)).all()
    return {
        "records": {
            str(r.group_no): {
                "score": r.score,
                "total": r.total,
                "finished_at": r.finished_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        }
    }


@router.post("/listening/progress")
def put_listening_progress(payload: ListeningProgressPut, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """保存一组听力训练的成绩;做完一轮即标记该组已完成(再练一次会覆盖成最近一次成绩)"""
    if payload.group_no < 1 or payload.group_no > listening_data.group_count():
        raise HTTPException(status_code=404, detail="这个分组不存在")
    row = db.scalar(select(ListeningRecord).where(
        ListeningRecord.user_id == user.id, ListeningRecord.group_no == payload.group_no))
    if row is None:
        row = ListeningRecord(user_id=user.id, group_no=payload.group_no)
        db.add(row)
    row.score = payload.score
    row.total = payload.total
    row.finished_at = datetime.now()
    db.commit()
    return {"group_no": row.group_no, "score": row.score, "total": row.total}


@router.post("/quiz/answer", response_model=QuizResult)
def quiz_answer(payload: QuizAnswer):
    """判断答案是否正确,返回正确释义"""
    result = quiz_data.check(payload.english, payload.answer)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在,请刷新页面")
    return result


@router.get("/word-lookup")
def word_lookup(word: str = ""):
    """点词查义:在高考/四级词库里查单词释义(自动还原变形、展开缩写)"""
    return word_index.lookup(word)


# ---------- 单词任务(支持多本词库) ----------

@router.get("/tasks/dictionaries")
def tasks_dictionaries():
    """任务模块的所有词库"""
    return dictionaries()


@router.get("/tasks/summary")
def tasks_summary(dict_key: str = "gaokao"):
    """某本词库的任务概览:单词总数、每组数量、分组数"""
    return {
        "dict": dict_key,
        "label": label(dict_key),
        "total": task_total(dict_key),
        "group_size": GROUP_SIZE,
        "groups": group_count(dict_key),
    }


@router.get("/tasks/words")
def task_words(dict_key: str = "gaokao", group: int = 1):
    """某本词库某一组的单词列表(组号从 1 开始)"""
    words = get_group(dict_key, group)
    if words is None:
        raise HTTPException(status_code=404, detail="这个分组不存在")
    return {"dict": dict_key, "group": group, "groups": group_count(dict_key), "words": words}


# ---------- 学习进度(按账号保存在服务器,前端整体替换) ----------

@router.get("/progress")
def get_progress(dict_key: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """读当前用户某本词库的进度;从未保存过返回 404(前端借此判断要不要迁移旧的浏览器数据)"""
    if dict_key not in DICTIONARIES:
        raise HTTPException(status_code=404, detail="词库不存在")
    row = db.scalar(select(UserProgress).where(
        UserProgress.user_id == user.id, UserProgress.dict_key == dict_key))
    if row is None:
        raise HTTPException(status_code=404, detail="还没有学习记录")
    return {"indices": json.loads(row.indices_json or "[]")}


@router.put("/progress")
def put_progress(payload: ProgressPut, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """整体替换某本词库的进度(每次保存把整组编号传上来,最后一次写入生效)"""
    if payload.dict_key not in DICTIONARIES:
        raise HTTPException(status_code=404, detail="词库不存在")
    row = db.scalar(select(UserProgress).where(
        UserProgress.user_id == user.id, UserProgress.dict_key == payload.dict_key))
    if row is None:
        row = UserProgress(user_id=user.id, dict_key=payload.dict_key, indices_json="[]")
        db.add(row)
    row.indices_json = json.dumps(sorted(set(payload.indices)))
    row.updated_at = datetime.now()
    db.commit()
    return {"indices": json.loads(row.indices_json)}
