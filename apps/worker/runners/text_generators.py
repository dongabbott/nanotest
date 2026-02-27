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
import random
import re
import string
import uuid


@dataclass(frozen=True)
class GeneratorResult:
    value: str


def now(fmt: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    return datetime.now(timezone.utc).strftime(fmt)


def random_text(n: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(max(0, int(n))))


def random_phone() -> str:
    # CN-like mobile: 1 + [3-9] + 9 digits
    return "1" + str(random.randint(3, 9)) + "".join(str(random.randint(0, 9)) for _ in range(9))


def random_email(domain: str = "example.com") -> str:
    local = "u" + "".join(str(random.randint(0, 9)) for _ in range(10))
    return f"{local}@{domain}"


def uuid4() -> str:
    return str(uuid.uuid4())


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

    if expr == "random_phone()":
        return random_phone()

    m = re.fullmatch(r"random_email\((.*)\)", expr)
    if m:
        raw = (m.group(1) or "").strip()
        if not raw:
            return random_email()
        domain = raw.strip().strip('"').strip("'")
        return random_email(domain=domain)

    if expr == "random_email()":
        return random_email()

    return None


GENERATORS = [
    {
        "id": "random_email",
        "signature": "random_email() | random_email(\"domain\")",
        "description": "生成随机邮箱（默认域 example.com，可指定域名）。",
        "examples": ["${random_email()}", "${random_email(\"test.com\")}"],
    },
    {
        "id": "random_phone",
        "signature": "random_phone()",
        "description": "生成随机手机号（CN-like：1[3-9]xxxxxxxxx）。",
        "examples": ["${random_phone()}"],
    },
    {
        "id": "random_text",
        "signature": "random_text(n)",
        "description": "生成随机字母数字文本，长度为 n。",
        "examples": ["${random_text(10)}"],
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
