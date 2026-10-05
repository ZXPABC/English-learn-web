"""数据库表结构"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Word(Base):
    """单词表"""
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    english: Mapped[str] = mapped_column(String(100))                     # 英文
    chinese: Mapped[str] = mapped_column(String(100))                     # 中文释义
    phonetic: Mapped[str] = mapped_column(String(100), default="")        # 音标
    example: Mapped[str] = mapped_column(Text, default="")                # 英文例句
    example_cn: Mapped[str] = mapped_column(Text, default="")             # 例句翻译
    category: Mapped[str] = mapped_column(String(50), default="未分类", index=True)  # 分类
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Lesson(Base):
    """课程表"""
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))                       # 标题
    summary: Mapped[str] = mapped_column(String(500), default="")         # 简介
    content: Mapped[str] = mapped_column(Text, default="")                # 英文正文
    content_cn: Mapped[str] = mapped_column(Text, default="")             # 中文翻译
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Admin(Base):
    """管理员账号表"""
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))  # 只存加密后的密码,不存明文


class User(Base):
    """学生用户表(前台注册,后台统一管理)"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))                # 只存加密后的密码,不存明文
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)         # 管理端可禁用账号
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)  # 最近登录时间


class UserProgress(Base):
    """用户学习进度:每个用户每本词库一行,已掌握单词编号存成 JSON 数组"""
    __tablename__ = "user_progress"
    __table_args__ = (UniqueConstraint("user_id", "dict_key", name="uq_user_dict"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    dict_key: Mapped[str] = mapped_column(String(30))                      # gaokao / cet4
    indices_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class QuizRecord(Base):
    """句子测验完成记录:每个用户每组一行(做完一轮即已完成,存最近一次成绩)"""
    __tablename__ = "quiz_records"
    __table_args__ = (UniqueConstraint("user_id", "group_no", name="uq_user_quiz_group"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_no: Mapped[int] = mapped_column()                                # 第几组(从 1 开始)
    score: Mapped[int] = mapped_column(default=0)                          # 最近一次答对题数
    total: Mapped[int] = mapped_column(default=0)                          # 该轮总题数
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class QuizDraft(Base):
    """句子测验中途退出的草稿:每个用户每组一份,下次点进该组自动接着做"""
    __tablename__ = "quiz_drafts"
    __table_args__ = (UniqueConstraint("user_id", "group_no", name="uq_user_quiz_draft"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_no: Mapped[int] = mapped_column()                                # 第几组(从 1 开始)
    draft_json: Mapped[str] = mapped_column(Text, default="{}")            # 题目列表+做到第几题+得分+错题
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ListeningRecord(Base):
    """听力训练完成记录:每个用户每组一行(做完一轮即已完成,存最近一次成绩)"""
    __tablename__ = "listening_records"
    __table_args__ = (UniqueConstraint("user_id", "group_no", name="uq_user_listening_group"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_no: Mapped[int] = mapped_column()                                # 第几组(从 1 开始)
    score: Mapped[int] = mapped_column(default=0)                          # 最近一次答对题数
    total: Mapped[int] = mapped_column(default=0)                          # 该轮总题数
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
