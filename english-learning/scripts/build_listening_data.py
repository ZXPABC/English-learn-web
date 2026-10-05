"""构建听力训练题库:从 Tatoeba 英中句对中筛选适合英语四级听力难度的句子

数据来源:https://www.manythings.org/anki/cmn-eng.zip(Tatoeba 语料,CC-BY 2.0)
筛选标准(和句子测验同源,但排除测验已用过的句子,偏爱短句更适合听):
  1. 英文 5~14 个单词,中文 4~30 个字符
  2. 中文转成简体
  3. 不含数字、不含句中大写专有名词(人名地名)
  4. 英文单词(去变形后)几乎全部在高考 3500 + 四级词库内(最多 1 个生词)
  5. 排除 app/data/quiz_sentences.json 里已经用过的句子
用法:
  python scripts/build_listening_data.py
"""
import io
import json
import random
import re
import sys
from pathlib import Path

from opencc import OpenCC

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "_quiz_raw" / "cmn.txt"
QUIZ = BASE / "app" / "data" / "quiz_sentences.json"
OUT = BASE / "app" / "data" / "listening_sentences.json"
TOTAL = 1000
GROUP_SIZE = 50

# 从项目里复用同一套缩写表与变形还原逻辑(app/word_lookup.py)
sys.path.insert(0, str(BASE))
from app.word_lookup import CONTRACTIONS, base_forms  # noqa: E402

cc = OpenCC("t2s")


def load_vocab() -> set:
    """高考 3500 + 四级词库的英文词(小写)"""
    vocab = set()
    for name in ("highschool3500.json", "cet4.json"):
        for w in json.loads((BASE / "app" / "data" / name).read_text(encoding="utf-8")):
            vocab.add(w["english"].strip().lower())
    return vocab


def english_ok(sentence: str, vocab: set) -> tuple[bool, int, int]:
    """英文句子是否合格:返回(是否合格, 单词数, 生词数)"""
    if re.search(r"\d", sentence):
        return False, 0, 0
    if "..." in sentence:
        return False, 0, 0
    # 还原缩写
    text = sentence.lower()
    for c, full in CONTRACTIONS.items():
        text = text.replace(c, full)
    # 拆词(去掉标点,连字符按空格拆)
    words = [w for w in re.split(r"[^a-z']+", text) if w]
    if not 5 <= len(words) <= 14:
        return False, len(words), 0
    # 句中大写专有名词检查(首词除外,I 除外)
    raw_words = sentence.split()
    for w in raw_words[1:]:
        if re.match(r"^[A-Z]", w):
            return False, len(words), 0
    # 生词统计(变形还原后仍不在词库)
    unknown = 0
    for w in words:
        if w == "i":
            continue
        if any(f in vocab for f in base_forms(w)):
            continue
        unknown += 1
    return unknown <= 1, len(words), unknown


def chinese_ok(text: str) -> bool:
    """中文译文是否合格:长度合适、简体、无英文"""
    text = cc.convert(text).strip()
    if not 4 <= len(text) <= 30:
        return False
    if re.search(r"[A-Za-z]", text):
        return False
    # 只允许汉字和常见标点
    if re.search(r"[^一-鿿0-9。,.!?;:、!?:…—\"''()()<>《》【】%+*/-]", text):
        return False
    return True


def main() -> None:
    vocab = load_vocab()
    used = {q["english"].lower() for q in json.loads(QUIZ.read_text(encoding="utf-8"))}
    print(f"词库词汇量(去重后): {len(vocab)},已用句子: {len(used)}")
    raw = io.open(RAW, encoding="utf-8").read().splitlines()
    pairs = []
    for line in raw:
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        en, zh, src = parts
        zh = cc.convert(zh).strip()
        if not chinese_ok(zh):
            continue
        ok, n_words, unknown = english_ok(en, vocab)
        if not ok:
            continue
        if en.lower() in used:
            continue
        pairs.append({"english": en, "chinese": zh, "src": src, "n": n_words, "u": unknown})
    print(f"通过筛选(且未用过)的句对数: {len(pairs)}")
    # 按英文去重
    seen, dedup = set(), []
    for p in pairs:
        key = p["english"].lower()
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    print(f"去重后: {len(dedup)}")
    # 优先全词库覆盖、句子偏短(听力更适合);同档内随机打散保证多样性
    rng = random.Random(20261005)
    rng.shuffle(dedup)
    dedup.sort(key=lambda p: (p["u"], abs(p["n"] - 7)))
    chosen = dedup[:TOTAL]
    chosen.sort(key=lambda p: p["n"])
    out = [{"english": p["english"], "chinese": p["chinese"], "src": p["src"]} for p in chosen]
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已选出 {len(out)} 道题,写入 {OUT.relative_to(BASE)}")
    print(f"每组 {GROUP_SIZE} 道,共 {len(out) // GROUP_SIZE} 组")
    print("\n--- 抽样检查 30 条 ---")
    for i in range(0, len(out), len(out) // 30):
        print(f"{out[i]['english']}  →  {out[i]['chinese']}")


if __name__ == "__main__":
    main()
