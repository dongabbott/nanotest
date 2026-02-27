"""Dynamic text/data generators for DSL expressions.

This module centralizes generator rules used by runners to build dynamic input values.

Supported expressions (examples):
  - random_email()
  - random_phone()
  - random_text(10)
  - uuid()
  - now(%Y%m%d%H%M%S)

Keep this file pure (no runner imports) so it can be reused across runners/services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional
from typing import Any
import random
import re
import string
import uuid

try:
    # Optional dependency. If not installed, we fall back to lightweight vocab generation.
    from faker import Faker  # type: ignore

    _FAKER_AVAILABLE = True
except Exception:  # pragma: no cover
    Faker = None  # type: ignore
    _FAKER_AVAILABLE = False


_faker_cache: dict[str, Any] = {}


def _get_faker(lang: str) -> Optional[Any]:
    """Return a cached Faker instance for requested language.

    lang:
      - 'en' -> en_US
      - 'zh' -> zh_CN
    """
    if not _FAKER_AVAILABLE:
        return None

    key = (lang or "en").lower()
    locale = "zh_CN" if key.startswith("zh") else "en_US"
    if locale not in _faker_cache:
        _faker_cache[locale] = Faker(locale)
    return _faker_cache[locale]


@dataclass(frozen=True)
class GeneratorResult:
    value: str


def now(fmt: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    return datetime.now(timezone.utc).strftime(fmt)


def _utc_date_parts() -> tuple[str, str, str]:
    """Return (yy, mm, dd) based on current UTC date."""
    dt = datetime.now(timezone.utc)
    yy = dt.strftime("%y")
    mm = dt.strftime("%m")
    dd = dt.strftime("%d")
    return yy, mm, dd


def random_text(n: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(max(0, int(n))))


def random_phone() -> str:
    """Generate phone by rule: 119 + yy + mm + dd + 2 random digits."""
    yy, mm, dd = _utc_date_parts()
    tail = "".join(str(random.randint(0, 9)) for _ in range(2))
    return f"119{yy}{mm}{dd}{tail}"


def random_email(region: Optional[str] = None, app: str = "timehut") -> str:
    """Generate email by rule:

    local-part: test + yy + mm + dd + 2 random digits

    domain:
      - app timehut  -> pp
      - app bebememo -> bb
      - default app -> pp

    suffix:
      - if region is falsy/None -> @{prefix}.com
      - else -> @{prefix}.{region} (region like tw.com/jp.com/kr.com)

    Examples:
      region=None, app=timehut  -> test26022712@pp.com
      region=tw.com, app=timehut -> test26022712@pp.tw.com
    """
    yy, mm, dd = _utc_date_parts()
    tail = "".join(str(random.randint(0, 9)) for _ in range(2))

    app_key = (app or "timehut").strip().lower()
    prefix = "pp" if app_key != "bebememo" else "bb"

    local = f"test{yy}{mm}{dd}{tail}"

    reg = (region or "").strip().lower()
    if not reg or reg == "null":
        return f"{local}@{prefix}.com"
    return f"{local}@{prefix}.{reg}"


def uuid4() -> str:
    return str(uuid.uuid4())


def sms_code() -> str:
    """Generate SMS code by strict rule required by product.

    Examples (based on current date):
      - 1/1   -> 1111
      - 12/1  -> 1211
      - 8/27  -> 8827

    Rule (strict):
      code = month + day + day
      - month: no zero-padding
      - day: no zero-padding

    Note:
      This intentionally differs from the common MMDD rule.
    """
    dt = datetime.now(timezone.utc)
    m = int(dt.strftime("%m")) # remove leading zero
    if m < 10:
        m = str(m) + str(m)

    d = int(dt.strftime("%d"))  # remove leading zero
    if d < 10:
        d = str(d) + str(d)
    return f"{m}{d}"


def _split_args(arg_str: str) -> list[str]:
    """Split a simple comma-separated argument list.

    Supports forms like:
      "tw.com", "timehut"
      tw.com, timehut
      'jp.com'

    This is intentionally lightweight (no full parser).
    """
    if arg_str is None:
        return []
    s = arg_str.strip()
    if not s:
        return []

    parts: list[str] = []
    current: list[str] = []
    quote: Optional[str] = None
    for ch in s:
        if quote:
            if ch == quote:
                quote = None
                continue
            current.append(ch)
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == ",":
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)

    last = "".join(current).strip()
    if last:
        parts.append(last)
    return parts


def eval_generator(expr: str) -> Optional[str]:
    """Evaluate a supported generator expression.

    Returns:
        Generated string if expr matches a known generator, else None.
    """
    expr = (expr or "").strip()

    if expr == "uuid()":
        return uuid4()

    m = re.fullmatch(r"now\((.*)\)", expr)
    if m:
        fmt = (m.group(1) or "%Y-%m-%dT%H%M%SZ").strip().strip('"').strip("'")
        return now(fmt)

    m = re.fullmatch(r"random_text\((\d+)\)", expr)
    if m:
        return random_text(int(m.group(1)))

    # semantic_text(20) / semantic_text(20, "zh")
    m = re.fullmatch(r"semantic_text\((.*)\)", expr)
    if m:
        raw = (m.group(1) or "").strip()
        if not raw:
            return semantic_text(20)
        args = _split_args(raw)
        if len(args) == 1:
            return semantic_text(int(args[0]))
        return semantic_text(int(args[0]), lang=args[1])

    # semantic_sentence() / semantic_sentence("zh")
    m = re.fullmatch(r"semantic_sentence\((.*)\)", expr)
    if m:
        raw = (m.group(1) or "").strip()
        if not raw:
            return semantic_sentence()
        args = _split_args(raw)
        return semantic_sentence(lang=args[0] if args else "en")

    if expr == "random_phone()":
        return random_phone()

    if expr == "sms_code()":
        return sms_code()

    # random_email()
    # random_email("tw.com")
    # random_email("tw.com", "timehut")
    # random_email(region="tw.com", app="timehut")  (lenient parsing)
    m = re.fullmatch(r"random_email\((.*)\)", expr)
    if m:
        raw = (m.group(1) or "").strip()
        if not raw:
            return random_email()

        # Support simple keyword args in any order (region/app)
        if "=" in raw:
            region_val: Optional[str] = None
            app_val: str = "timehut"
            for chunk in raw.split(","):
                if "=" not in chunk:
                    continue
                k, v = chunk.split("=", 1)
                key = k.strip().lower()
                val = v.strip().strip('"').strip("'")
                if key == "region":
                    region_val = val
                elif key == "app":
                    app_val = val
            return random_email(region=region_val, app=app_val)

        args = _split_args(raw)
        if len(args) == 1:
            return random_email(region=args[0])
        if len(args) >= 2:
            return random_email(region=args[0], app=args[1])
        return random_email()

    if expr == "random_email()":
        return random_email()

    return None


GENERATORS = [
    {
        "id": "random_email",
        "signature": "random_email() | random_email(\"region\") | random_email(\"region\", \"app\")",
        "description": "生成随机邮箱（本地部分：test+yyMMdd+2位随机；域：timehut->pp, bebememo->bb；可选地区如 tw.com/jp.com/kr.com）。",
        "examples": [
            "${random_email()}",
            "${random_email(\"tw.com\")}",
            "${random_email(\"tw.com\", \"timehut\")}",
            "${random_email(\"jp.com\", \"bebememo\")}",
        ],
    },
    {
        "id": "random_phone",
        "signature": "random_phone()",
        "description": "生成随机手机号（规则：119 + yy + mm + dd + 2位随机）。",
        "examples": ["${random_phone()}"],
    },
    {
        "id": "sms_code",
        "signature": "sms_code()",
        "description": "生成短信验证码（规则：当日 月+日+日；月不补0，日不补0，如 1/1->1111, 12/1->1211, 8/27->8827）。",
        "examples": ["${sms_code()}"],
    },
    {
        "id": "random_text",
        "signature": "random_text(n)",
        "description": "生成随机字母数字文本，长度为 n。",
        "examples": ["${random_text(10)}"],
    },
    {
        "id": "semantic_text",
        "signature": "semantic_text(n, lang)",
        "description": "生成有语义的中文/英文文本（非乱码），长度接近 n（字符数，best-effort）；lang 可为 'en' 或 'zh'。",
        "examples": ["${semantic_text(30)}", "${semantic_text(30, \"zh\")}"],
    },
    {
        "id": "semantic_sentence",
        "signature": "semantic_sentence(lang)",
        "description": "生成一条简短有语义的句子；lang 可为 'en' 或 'zh'。",
        "examples": ["${semantic_sentence()}", "${semantic_sentence(\"zh\")}"],
    },
    {
        "id": "uuid",
        "signature": "uuid()",
        "description": "生成 UUID v4 字符串。",
        "examples": ["${uuid()}"],
    },
    {
        "id": "now",
        "signature": "now(fmt)",
        "description": "生成当前 UTC 时间字符串（strftime 格式）。",
        "examples": ["${now(%Y%m%d%H%M%S)}"],
    },
]

# Lightweight semantic corpora (no external deps)
_EN_WORDS = [
    "time",
    "note",
    "memory",
    "schedule",
    "daily",
    "focus",
    "plan",
    "record",
    "story",
    "task",
    "reminder",
    "message",
    "health",
    "travel",
    "photo",
    "meeting",
    "progress",
    "review",
    "idea",
    "simple",
    "clear",
    "quick",
    "safe",
    "sync",
    "backup",
]

_ZH_WORDS = [
    "今天",
    "记录",
    "计划",
    "提醒",
    "日程",
    "备忘",
    "心情",
    "习惯",
    "学习",
    "工作",
    "进度",
    "复盘",
    "目标",
    "会议",
    "出行",
    "健康",
    "照片",
    "同步",
    "备份",
    "简单",
    "清晰",
    "快速",
    "安全",
    "重要",
    "建议",
]


def _join_words(words: list[str], lang: str) -> str:
    if lang.lower().startswith("zh"):
        return "".join(words)
    return " ".join(words)


def semantic_text(n: int, lang: str = "en") -> str:
    """Generate *semantic-ish* text (Chinese or English) with a target length.

    Args:
        n: target length in characters (best-effort). If n <= 0 -> "".
        lang: 'en' or 'zh' (also accepts 'english'/'chinese').

    Notes:
        - No external dependencies; uses small built-in vocab.
        - Best-effort length: will generate a sentence-like text close to n.
    """
    n = int(n)
    if n <= 0:
        return ""

    lang_key = "zh" if lang and lang.lower().startswith("zh") else "en"

    fake = _get_faker(lang_key)
    if fake is not None:
        # Faker handles max length. It may produce slightly shorter text; pad with more text if needed.
        chunks: list[str] = []
        while True:
            chunks.append(fake.text(max_nb_chars=n))
            txt = ("".join(chunks) if lang_key == "zh" else " ".join(chunks)).strip()
            if len(txt) >= n:
                return txt[:n]

    vocab = _ZH_WORDS if lang_key == "zh" else _EN_WORDS

    # Build in chunks to approach target length.
    out: list[str] = []
    while True:
        # sentence length in words/phrases
        k = random.randint(6, 12)
        words = [random.choice(vocab) for _ in range(k)]
        sentence = _join_words(words, lang_key)
        # add punctuation
        sentence += "。" if lang_key == "zh" else "."
        out.append(sentence)

        text = ("".join(out) if lang_key == "zh" else " ".join(out)).strip()
        if len(text) >= n:
            return text[:n]


def semantic_sentence(lang: str = "en") -> str:
    """Generate a single short sentence."""
    lang_key = "zh" if lang and (lang.lower().startswith("zh")) else "en"
    fake = _get_faker(lang_key)
    if fake is not None:
        s = fake.sentence().strip()
        if lang_key == "zh":
            return s.rstrip("。").rstrip(".") + "。"
        return s.rstrip(".") + "."

    return semantic_text(60, lang=lang).rstrip(".").rstrip("。").strip() + (
        "。" if lang_key == "zh" else "."
    )


if __name__ == "__main__":
    # quick manual check
    print("sms:", sms_code())
    print("sem en:", semantic_text(80, "en"))
    print("sem zh:", semantic_text(40, "zh"))