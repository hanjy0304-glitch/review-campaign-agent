"""서버(GitHub Actions) 완전 자동 수집기 모음.

사이트 계정은 환경변수(<KEY>_ID / <KEY>_PW)가 있을 때만 쓰고, 값은 출력하지 않는다.
새 사이트를 붙이려면 `base.Collector` 를 구현해 `COLLECTORS` 에 등록한다 (docs/add-site.md).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

import httpx

from ..catalog import Site
from ..models import Campaign
from .base import CollectError, Collector, LoginError
from .dinnerqueen import DinnerqueenCollector
from .gangnam import GangnamCollector
from .popomon import PopomonCollector
from .reviewplace import ReviewplaceCollector
from .seoulouba import SeouloubaCollector

COLLECTORS: dict[str, type[Collector]] = {
    c.key: c
    for c in (
        GangnamCollector,
        DinnerqueenCollector,
        ReviewplaceCollector,
        PopomonCollector,
        SeouloubaCollector,
    )
}

OK = "ok"
SKIPPED = "skipped"
ERROR = "error"


@dataclass
class SiteReport:
    """사이트 한 곳의 수집 결과. 로그에 그대로 쓰이므로 계정 정보·캠페인명은 담지 않는다."""

    key: str
    name: str
    status: str
    count: int = 0
    added: int = 0
    updated: int = 0
    message: str = ""
    campaigns: list[Campaign] = field(default_factory=list, repr=False)


def _credential_names(cls: type[Collector]) -> tuple[str, str]:
    key = cls.key.upper()
    return f"{key}_ID", f"{key}_PW"


def collect_sites(
    sites: Iterable[Site],
    env: Mapping[str, str],
    today: date,
    client_factory=None,
) -> list[SiteReport]:
    """수집기가 있는 사이트만 돌린다. 한 사이트가 실패해도 나머지는 계속한다.

    계정 환경변수가 없는 사이트는 '건너뜀'으로 남긴다(설정하지 않은 사용자는 조용히 지나간다).
    """
    reports: list[SiteReport] = []
    for site in sites:
        cls = COLLECTORS.get(site.key)
        if cls is None:
            continue
        id_name, pw_name = _credential_names(cls)
        if not cls.configured(env):
            reports.append(SiteReport(cls.key, cls.name, SKIPPED, message=f"{id_name} / {pw_name} 가 없습니다"))
            continue
        client = client_factory(cls) if client_factory else None
        try:
            campaigns = cls.from_env(env).collect(today, client=client)
        except LoginError as e:
            reports.append(SiteReport(cls.key, cls.name, ERROR, message=str(e)))
        except (CollectError, httpx.HTTPError) as e:
            reason = e if isinstance(e, CollectError) else type(e).__name__
            reports.append(SiteReport(cls.key, cls.name, ERROR, message=str(reason)))
        else:
            reports.append(SiteReport(cls.key, cls.name, OK, count=len(campaigns), campaigns=campaigns))
        finally:
            if client is not None:
                client.close()
    return reports


def run_collection(
    store,
    sites: Iterable[Site],
    env: Mapping[str, str],
    today: date,
    dry_run: bool = False,
    client_factory=None,
) -> list[SiteReport]:
    """수집한 뒤 Notion 표에 반영한다. dry_run 이면 세션만 확인하고 저장하지 않는다."""
    reports = collect_sites(sites, env, today, client_factory=client_factory)
    if store is None or dry_run:
        return reports
    rows = store.fetch_rows()
    for report in reports:
        if report.status == OK and report.campaigns:
            report.added, report.updated = store.upsert_collected(report.campaigns, rows)
    return reports


def format_reports(reports: Iterable[SiteReport]) -> list[str]:
    lines: list[str] = []
    for r in reports:
        if r.status == OK:
            detail = f"{r.count}건 확인"
            if r.added or r.updated:
                detail += f" (새로 추가 {r.added}, 갱신 {r.updated})"
            lines.append(f"{r.name}: {detail}")
        elif r.status == SKIPPED:
            lines.append(f"{r.name}: 건너뜀 — {r.message}")
        else:
            lines.append(f"{r.name}: 실패 — {r.message}")
    return lines


def has_error(reports: Iterable[SiteReport]) -> bool:
    return any(r.status == ERROR for r in reports)


__all__ = [
    "COLLECTORS",
    "Collector",
    "ERROR",
    "OK",
    "SKIPPED",
    "SiteReport",
    "collect_sites",
    "format_reports",
    "has_error",
    "run_collection",
]
