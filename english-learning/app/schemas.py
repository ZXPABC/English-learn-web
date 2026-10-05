"""接口的请求/响应数据格式(Pydantic 模型)"""
from datetime import datetime

from pydantic import BaseModel


# ---------- 单词 ----------

class WordOut(BaseModel):
    """返回给前端的单词数据"""
    id: int
    english: str
    chinese: str
    phonetic: str
    example: str
    example_cn: str
    category: str

    model_config = {"from_attributes": True}  # 允许直接从数据库对象转换


class WordCreate(BaseModel):
    """新建单词"""
    english: str
    chinese: str
    phonetic: str = ""
    example: str = ""
    example_cn: str = ""
    category: str = "未分类"


class WordUpdate(BaseModel):
    """更新单词:只传要修改的字段"""
    english: str | None = None
    chinese: str | None = None
    phonetic: str | None = None
    example: str | None = None
    example_cn: str | None = None
    category: str | None = None


# ---------- 课程 ----------

class LessonOut(BaseModel):
    """返回给前端的课程数据"""
    id: int
    title: str
    summary: str
    content: str
    content_cn: str

    model_config = {"from_attributes": True}


class LessonCreate(BaseModel):
    """新建课程"""
    title: str
    summary: str = ""
    content: str = ""
    content_cn: str = ""


class LessonUpdate(BaseModel):
    """更新课程"""
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    content_cn: str | None = None


# ---------- 句子测验 ----------

class QuizQuestion(BaseModel):
    """测验题目:一个英文句子 + 4 个中文选项"""
    english: str
    chinese: str
    options: list[str]


class QuizAnswer(BaseModel):
    """用户提交的答案"""
    english: str
    answer: str


class QuizResult(BaseModel):
    """判分结果"""
    correct: bool
    correct_answer: str
    english: str


# ---------- 用户 ----------

class ProgressPut(BaseModel):
    """上传某本词库的学习进度(整体替换)"""
    dict_key: str
    indices: list[int]


class UserOut(BaseModel):
    """用户管理列表里的一行"""
    id: int
    username: str
    created_at: datetime
    last_login: datetime | None
    is_active: bool
    mastered_count: int = 0


class ResetPassword(BaseModel):
    """管理员重置用户密码"""
    password: str


class QuizProgressPut(BaseModel):
    """上报一组句子测验的成绩(做完一轮即标记该组已完成)"""
    group_no: int
    score: int
    total: int


class QuizDraftPut(BaseModel):
    """保存一组测验中途退出的草稿(下次点进该组恢复)"""
    group_no: int
    draft: dict


class ListeningProgressPut(BaseModel):
    """上报一组听力训练的成绩(做完一轮即标记该组已完成)"""
    group_no: int
    score: int
    total: int
