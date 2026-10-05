"""测验题库:看英文句子选中文意思

题目在 app/data/quiz_sentences.json(由 scripts/build_quiz_data.py 生成,
数据来源 Tatoeba 开放语料,筛选标准见该脚本),启动时一次性加载到内存,
和任务词库一样不占数据库。
"""
import json
import random
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "quiz_sentences.json"
GROUP_SIZE = 50

_questions: list[dict] = []   # [{"english", "chinese", "src"}]
_index: dict[str, str] = {}   # 英文句子 -> 中文释义(判分用)


def load() -> None:
    """启动时把题库读进内存"""
    global _questions, _index
    _questions = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    _index = {q["english"]: q["chinese"] for q in _questions}


def total() -> int:
    """题目总数"""
    return len(_questions)


def group_count() -> int:
    """分组数"""
    return (len(_questions) + GROUP_SIZE - 1) // GROUP_SIZE


def _make_options(answer: dict, pool: list[dict]) -> list[str]:
    """给一句答案造 4 个中文选项:正确答案 + 3 个干扰项(打乱顺序)

    干扰项优先取同一组里中文不同的句子,不够时从整个题库补充。
    """
    seen = {answer["chinese"]}
    others = [q for q in pool if q["chinese"] not in seen]
    if len(others) < 3:
        # 组内干扰项不够时,从整个题库补充
        for q in _questions:
            if q["chinese"] in seen:
                continue
            seen.add(q["chinese"])
            others.append(q)
            if len(others) >= 3:
                break
    distractors = random.sample(others, 3)
    options = [answer["chinese"]] + [q["chinese"] for q in distractors]
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
    return {"english": answer["english"], "chinese": answer["chinese"], "options": _make_options(answer, pool)}


def group_questions(group_no: int) -> list[dict]:
    """某一组(从 1 开始)的全部题目,每题带 4 个中文选项,顺序打乱

    选组测验时一轮做完这一整组;组号不存在时返回空列表。
    """
    pool = get_group(group_no)
    if not pool:
        return []
    qs = [{"english": q["english"], "chinese": q["chinese"], "options": _make_options(q, pool)} for q in pool]
    random.shuffle(qs)
    return qs


def get_group(group_no: int) -> list[dict]:
    """某一组(从 1 开始)的题目;组号不存在时返回空列表"""
    if group_no < 1 or group_no > group_count():
        return []
    start = (group_no - 1) * GROUP_SIZE
    return _questions[start:start + GROUP_SIZE]


def check(english: str, answer: str) -> dict | None:
    """判断答案:按英文句子找到题目,比对中文释义"""
    chinese = _index.get(english)
    if chinese is None:
        return None
    return {"correct": chinese == answer, "correct_answer": chinese, "english": english}
