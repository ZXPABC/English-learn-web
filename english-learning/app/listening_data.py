"""听力训练题库:听英文句子,从中文选项里选出正确意思

题目在 app/data/listening_sentences.json(由 scripts/build_listening_data.py 生成,
数据来源 Tatoeba 开放语料,筛选标准见该脚本),启动时一次性加载到内存,
和任务词库一样不占数据库。

干扰项设计:从"听力题库 + 测验题库"的全部中文句子里,按与正确答案的
实词重叠度挑干扰项——两句中文重合的词越多,听一个关键词就越难锁定答案,
逼着听完整句(比如"做作业"同时出现在两个选项里,听到 homework 也没法直接选)。
"""
import json
import random
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "listening_sentences.json"
QUIZ_DATA_FILE = Path(__file__).parent / "data" / "quiz_sentences.json"
GROUP_SIZE = 50

# 重叠度计算时忽略的常见虚字(和标点):只比"实词"字符,避免所有句子都因"的我了"重合
_STOP_CHARS = set("的我了是在他她你您有和就不个这那要也都很能会去说看没有上下来到对吗呢吧啊一几些什么怎么为把被让再又才还点儿东西天年时候人家里")

_questions: list[dict] = []                    # [{"english", "chinese", "src"}]
_distractors: list[tuple[str, set[str]]] = []  # 干扰项池:(中文, 实词字符集合),去重


def _content_chars(s: str) -> list[str]:
    """中文句子里去掉虚字和标点后的实词字符"""
    return [c for c in s if "一" <= c <= "鿿" and c not in _STOP_CHARS]


def load() -> None:
    """启动时把题库读进内存,并建好干扰项索引"""
    global _questions, _distractors
    _questions = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    quiz = json.loads(QUIZ_DATA_FILE.read_text(encoding="utf-8"))
    seen = set()
    for q in _questions + quiz:
        zh = q["chinese"]
        if zh in seen:
            continue
        seen.add(zh)
        _distractors.append((zh, set(_content_chars(zh))))


def total() -> int:
    """题目总数"""
    return len(_questions)


def group_count() -> int:
    """分组数"""
    return (len(_questions) + GROUP_SIZE - 1) // GROUP_SIZE


def get_group(group_no: int) -> list[dict]:
    """某一组(从 1 开始)的题目;组号不存在时返回空列表"""
    if group_no < 1 or group_no > group_count():
        return []
    start = (group_no - 1) * GROUP_SIZE
    return _questions[start:start + GROUP_SIZE]


def _overlap(ans_chars: list[str], cand_chars: set[str]) -> int:
    """两个中文句子的实词重叠字符数"""
    return sum(1 for c in ans_chars if c in cand_chars)


def _make_options(answer: dict) -> list[str]:
    """给一句答案造 4 个中文选项:正确答案 + 3 个"意思接近"的干扰项(打乱顺序)

    干扰项按与正确答案的实词重叠度从高到低排,取前 15 个里随机 3 个
    (同一道题每次选项略有变化);一个都找不到重合时才从题库随机补。
    """
    ans_zh = answer["chinese"]
    ans_chars = _content_chars(ans_zh)
    scored: list[tuple[int, str]] = []
    for zh, chars in _distractors:
        if zh == ans_zh:
            continue
        ov = _overlap(ans_chars, chars)
        if ov > 0:
            scored.append((ov, zh))
    scored.sort(key=lambda x: -x[0])
    top = [zh for _, zh in scored[:15]]
    random.shuffle(top)
    picked = top[:3]
    if len(picked) < 3:
        others = [zh for zh, _ in _distractors if zh != ans_zh and zh not in picked]
        random.shuffle(others)
        picked += others[:3 - len(picked)]
    options = [ans_zh] + picked
    random.shuffle(options)
    return options


def make_question(group_no: int = 0) -> dict:
    """随机出一题:英文句子 + 4 个中文选项

    group_no=0 表示从全部题目随机;>0 表示只在指定组内随机。
    """
    pool = _questions if group_no <= 0 else get_group(group_no)
    if not pool:
        return {}
    answer = random.choice(pool)
    return {"english": answer["english"], "chinese": answer["chinese"], "options": _make_options(answer)}


def group_questions(group_no: int) -> list[dict]:
    """某一组(从 1 开始)的全部题目,每题带 4 个中文选项,顺序打乱

    选组训练时一轮做完这一整组;组号不存在时返回空列表。
    """
    pool = get_group(group_no)
    if not pool:
        return []
    qs = [{"english": q["english"], "chinese": q["chinese"], "options": _make_options(q)} for q in pool]
    random.shuffle(qs)
    return qs
