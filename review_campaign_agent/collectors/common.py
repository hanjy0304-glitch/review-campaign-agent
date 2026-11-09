"""사이트 수집기가 함께 쓰는 파싱 도우미.

카드를 찾는 규칙은 크롬 확장(extension/src/*_parse.js)과 같게 유지한다.
클래스 이름은 사이트 개편 때마다 바뀌므로 쓰지 않고, **캠페인 상세로 가는 링크 주소**와
**마감 문구(D-n, n일 남음, 오늘까지, 날짜)** 로 카드를 찾는다.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from ..notion_schema import KINDS

# 마감을 나타내는 문구. 카드를 찾을 때와 남은 일수를 읽을 때 같은 기준을 쓴다.
DDAY_RE = re.compile(
    r"D\s*-\s*\d+|D\s*-?\s*day|D\s*\+\s*\d+|\d+\s*일\s*남음|오늘\s*(?:까지|마감)"
    r"|\d+\s*일\s*지남|~\s*\d{1,2}\s*[./]\s*\d{1,2}|\d{1,2}\s*[./]\s*\d{1,2}\s*(?:까지|마감)",
    re.I,
)
APPLY_RE = re.compile(r"신청\s*\d+")


def norm(text: str) -> str:
    """여러 줄·연속 공백을 한 칸으로 줄인다 (카드 글에서 문구를 찾기 쉽게)."""
    return re.sub(r"\s+", " ", text or "").strip()


def _days_until(month: int, day: int, today: date) -> int | None:
    """'11.11'처럼 연도가 없는 날짜를 남은 일수로. 오늘과 가까운 쪽(작년/올해/내년)으로 고른다."""
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        target = date(today.year, month, day)
    except ValueError:  # 2월 30일 같은 잘못된 날짜
        return None
    if target < today - timedelta(days=183):
        try:
            target = date(today.year + 1, month, day)
        except ValueError:
            return None
    return (target - today).days


def days_left(text: str, today: date | None = None) -> int | None:
    """카드 문구에서 마감까지 남은 일수. D-3 → 3, 오늘마감 → 0, D+2(지남) → -2.

    today 를 주면 '11.11 까지'·'11.05 ~ 11.11' 같은 날짜 표기도 남은 일수로 바꾼다.
    """
    text = norm(text)
    m = re.search(r"D\s*-\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1))
    if re.search(r"D\s*-?\s*day", text, re.I):
        return 0
    m = re.search(r"(\d+)\s*일\s*남음", text)
    if m:
        return int(m.group(1))
    if re.search(r"오늘\s*(?:까지|마감)", text):
        return 0
    m = re.search(r"(\d+)\s*일\s*지남", text)
    if m:
        return -int(m.group(1))
    m = re.search(r"D\s*\+\s*(\d+)", text, re.I)
    if m:
        return -int(m.group(1))
    if today is None:
        return None
    # '11.05 ~ 11.11'(모집기간)은 뒤 날짜가 마감, '11.11 까지'·'11.11 마감'은 그 날이 마감이다.
    m = re.search(r"~\s*(\d{1,2})\s*[./]\s*(\d{1,2})", text)
    if m:
        return _days_until(int(m.group(1)), int(m.group(2)), today)
    m = re.search(r"(\d{1,2})\s*[./]\s*(\d{1,2})\s*(?:까지|마감)", text)
    if m:
        return _days_until(int(m.group(1)), int(m.group(2)), today)
    return None


def site_path(href: str) -> str:
    """절대 주소를 사이트 안 경로로 바꾼다 (Notion 링크 칸을 한 가지 형태로 두기 위해)."""
    if href.startswith("http"):
        parts = urlsplit(href)
        return parts.path + (f"?{parts.query}" if parts.query else "")
    return href if href.startswith("/") else "/" + href


def card_for(anchor, selector: str, id_re: re.Pattern[str], marker: re.Pattern[str] = DDAY_RE):
    """링크 하나가 속한 카드 덩어리.

    같은 캠페인 링크만 있는(다른 캠페인 링크가 없는) 가장 작은 상위 요소 중 마감 문구를 담은 것.
    마감 문구가 없는 카드(마감된 캠페인 등)는 링크를 감싸는 가장 작은 요소를 쓴다.
    """
    el = anchor.parent
    fallback = None
    while el is not None and getattr(el, "name", None) not in (None, "body", "html", "[document]"):
        ids = {
            m.group(1)
            for a in el.select(selector)
            if (m := id_re.search(a.get("href") or "")) is not None
        }
        if len(ids) > 1:
            break
        if fallback is None:
            fallback = el
        if marker.search(norm(el.get_text(" "))):
            return el
        el = el.parent
    return fallback or anchor


def normalize_kind(text: str) -> str | None:
    """사이트마다 다른 유형 표기를 Notion 표의 유형 선택지(방문형·배송형·구매평·기자단)로 맞춘다.

    표에 없는 값을 그대로 넣으면 선택지가 제멋대로 늘어나므로, 확실한 것만 쓰고 나머지는 비운다.
    """
    text = norm(text)
    for kind, words in (
        ("구매평", ("구매평", "구매형", "구매")),
        ("방문형", ("방문형",)),
        ("배송형", ("배송형", "배송")),
        ("기자단", ("기자단",)),
    ):
        if kind in KINDS and any(w in text for w in words):
            return kind
    return None


__all__ = [
    "APPLY_RE",
    "DDAY_RE",
    "card_for",
    "days_left",
    "norm",
    "normalize_kind",
    "site_path",
]
