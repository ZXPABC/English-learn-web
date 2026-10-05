"""点词查义:句子测验里点击单词查看中文释义

数据来自高考 3500 + 四级两本词库(和任务模块同一批数据),
启动时加载进内存;查词时自动还原常见变形(复数、过去式、ing 等),
缩写(don't 等)会展开成两个词分别查义。
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# 常见缩写展开,便于逐词查义(don't -> do not)
CONTRACTIONS = {
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "don't": "do not", "doesn't": "does not", "didn't": "did not", "can't": "can not",
    "couldn't": "could not", "won't": "will not", "wouldn't": "would not",
    "shouldn't": "should not", "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not", "it's": "it is", "that's": "that is", "what's": "what is",
    "he's": "he is", "she's": "she is", "there's": "there is", "let's": "let us",
    "i'm": "i am", "i'll": "i will", "i've": "i have", "i'd": "i would",
    "you'll": "you will", "you're": "you are", "we're": "we are",
    "they're": "they are", "we'll": "we will", "they'll": "they will",
}

_index: dict[str, dict] = {}  # 小写英文 -> {"english", "phonetic", "chinese"}


def _add(word: str, entry: dict) -> None:
    """把一个词(或词形)写入索引,释义沿用整个词条"""
    key = word.strip().lower()
    if key:
        _index[key] = {"english": word.strip(), "phonetic": entry["phonetic"], "chinese": entry["chinese"]}


def load() -> None:
    """启动时把两本词库读进内存,做成查词索引

    词表里有些不规则动词/形容词的变形写在一个词条里(如 "make made made"),
    拆开后每个形式都能查到;普通短语(如 "bank account")只按整条索引,
    避免查单个词时误中短语的释义。
    """
    global _index
    _index = {}
    for name in ("highschool3500.json", "cet4.json"):
        for entry in json.loads((DATA_DIR / name).read_text(encoding="utf-8")):
            en = entry["english"].strip()
            if not en:
                continue
            if "=" in en:
                # "bike = bicycle" 这种等号词条:两边分别索引
                for side in en.split("="):
                    _add(side, entry)
            elif "过去式" in entry["chinese"] or "比较级" in entry["chinese"]:
                # 变形词条(释义带【一般现在 过去式 过去分词】等标注):每个形式单独索引
                for form in en.split():
                    _add(form, entry)
            else:
                # 普通短语:只按整条索引
                _add(en, entry)


def base_forms(word: str) -> list[str]:
    """一个单词可能的基础形式(原形在前,变形逐级尝试)"""
    cands = [word]
    if len(word) > 3:
        if word.endswith("ies"):
            cands.append(word[:-3] + "y")
        if word.endswith("es"):
            cands.append(word[:-2])
        if word.endswith("s") and not word.endswith("ss"):
            cands.append(word[:-1])
        if word.endswith("ed"):
            cands.append(word[:-2])
            cands.append(word[:-1])  # liked -> like
        if word.endswith("ing") and len(word) > 4:
            stem = word[:-3]
            cands.append(stem)
            cands.append(stem + "e")  # making -> make
            if len(stem) > 1 and stem[-1] == stem[-2]:  # running -> run
                cands.append(stem[:-1])
        if word.endswith("ly"):
            cands.append(word[:-2])
        if word.endswith("er"):
            cands.append(word[:-2])
            cands.append(word[:-1])
        if word.endswith("est"):
            cands.append(word[:-3])
            cands.append(word[:-2])
    return cands


def _lookup_one(word: str) -> dict | None:
    """查一个单词(先原形,再逐级还原变形)"""
    for cand in base_forms(word):
        if cand in _index:
            return _index[cand]
    return None


def lookup(word: str) -> dict:
    """查词入口:支持缩写展开;返回 {'word', 'phonetic', 'chinese', 'found'}"""
    cleaned = word.strip().strip(".,!?;:()\"'")
    if not cleaned:
        return {"word": word, "phonetic": "", "chinese": "词库中未收录", "found": False}
    parts = CONTRACTIONS.get(cleaned.lower(), cleaned.lower()).split()
    hits = [r for r in (_lookup_one(p) for p in parts) if r]
    if not hits:
        return {"word": cleaned, "phonetic": "", "chinese": "词库中未收录这个词", "found": False}
    return {
        "word": cleaned,
        "phonetic": " · ".join(h["phonetic"] for h in hits if h.get("phonetic")),
        "chinese": " + ".join(h["chinese"] for h in hits),
        "found": True,
    }
