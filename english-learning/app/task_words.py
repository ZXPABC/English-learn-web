"""任务词库数据:支持多本词库,每本从 JSON 文件加载到内存(只读一次)"""
import json
from pathlib import Path

from fastapi import HTTPException

DATA_DIR = Path(__file__).resolve().parent / "data"
GROUP_SIZE = 30  # 每组单词数(建议每天学一组)

# 词库配置:key -> (显示名称, 数据文件名)
DICTIONARIES = {
    "gaokao": {"label": "高考 3500 词", "file": "highschool3500.json"},
    "cet4": {"label": "大学英语四级", "file": "cet4.json"},
}

_cache: dict[str, list[dict]] = {}


def label(dict_key: str) -> str:
    """词库显示名称"""
    if dict_key not in DICTIONARIES:
        raise HTTPException(status_code=404, detail="词库不存在")
    return DICTIONARIES[dict_key]["label"]


def dictionaries() -> list[dict]:
    """所有词库的概要信息"""
    return [
        {"key": key, "label": info["label"], "total": total(key), "groups": group_count(key)}
        for key, info in DICTIONARIES.items()
    ]


def load_words(dict_key: str) -> list[dict]:
    """加载某本词库(只读一次文件,之后走内存缓存)"""
    if dict_key not in DICTIONARIES:
        raise HTTPException(status_code=404, detail="词库不存在")
    if dict_key not in _cache:
        path = DATA_DIR / DICTIONARIES[dict_key]["file"]
        with open(path, encoding="utf-8") as f:
            _cache[dict_key] = json.load(f)
    return _cache[dict_key]


def total(dict_key: str) -> int:
    """某本词库的单词总数"""
    return len(load_words(dict_key))


def group_count(dict_key: str) -> int:
    """某本词库的分组数"""
    return (total(dict_key) + GROUP_SIZE - 1) // GROUP_SIZE


def get_group(dict_key: str, group_no: int) -> list[dict] | None:
    """取某本词库某一组的单词(组号从 1 开始),每个单词带全局编号"""
    if dict_key not in DICTIONARIES:
        return None
    if group_no < 1 or group_no > group_count(dict_key):
        return None
    start = (group_no - 1) * GROUP_SIZE
    end = min(start + GROUP_SIZE, total(dict_key))
    result = []
    for i in range(start, end):
        w = load_words(dict_key)[i]
        result.append({
            "index": i,  # 全局编号(从 0 开始),前端用它记录学习进度
            "english": w["english"],
            "phonetic": w["phonetic"],
            "chinese": w["chinese"],
        })
    return result
