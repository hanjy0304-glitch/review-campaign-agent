"""서버 수집기(GitHub Actions) 공통 뼈대.

사이트 계정은 환경변수로만 받는다 (<KEY>_ID / <KEY>_PW). 값은 오류 메시지·Actions 로그에 남기지 않는다.
로그인 세션(쿠키)은 수집하는 동안 메모리에만 있고 어디에도 저장하지 않는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import date

import httpx

from ..models import Campaign

# 사이트가 기본 파이썬 클라이언트를 막는 경우가 있어 일반 브라우저로 보이게 한다.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT = 20.0


class CollectError(Exception):
    """수집 실패. 메시지는 그대로 Actions 로그에 남으므로 계정 정보를 넣지 않는다."""


class LoginError(CollectError):
    """로그인 실패(계정 정보 불일치·차단·세션 만료)."""


def new_client(origin: str) -> httpx.Client:
    """사이트 쿠키를 유지하는 클라이언트."""
    return httpx.Client(
        base_url=origin,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


class Collector(ABC):
    """사이트 하나의 수집기. 하위 클래스가 key·name·origin 과 _collect 를 채운다."""

    key: str = ""
    name: str = ""
    origin: str = ""

    def __init__(self, site_id: str, password: str) -> None:
        if not site_id or not password:
            raise LoginError(f"{self.name} 계정 정보가 비어 있습니다.")
        self._id = site_id
        self._password = password

    @classmethod
    def configured(cls, env: Mapping[str, str]) -> bool:
        """계정 환경변수가 둘 다 있는지. 값은 읽기만 하고 출력하지 않는다."""
        return bool(env.get(f"{cls.key.upper()}_ID") and env.get(f"{cls.key.upper()}_PW"))

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Collector":
        return cls(env.get(f"{cls.key.upper()}_ID", ""), env.get(f"{cls.key.upper()}_PW", ""))

    def collect(self, today: date, client: httpx.Client | None = None) -> list[Campaign]:
        """선정 내역을 수집해 Campaign 목록으로 돌려준다. client 는 테스트에서 갈아 끼운다."""
        if client is not None:
            return self._collect(client, today)
        with new_client(self.origin) as own:
            return self._collect(own, today)

    @abstractmethod
    def _collect(self, client: httpx.Client, today: date) -> list[Campaign]:
        """로그인 후 목록 화면을 읽어 Campaign 으로 만든다."""
