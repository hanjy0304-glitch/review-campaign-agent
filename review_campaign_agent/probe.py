"""로그인 없이 카탈로그 사이트에 접속되는지 확인한다 (GitHub Actions 해외 IP 차단 여부 점검용).

사이트 첫 화면만 GET 으로 한 번 요청한다. 로그인·계정 정보·개인 데이터는 쓰지 않는다.
"""

from dataclasses import dataclass

import httpx

from .catalog import Site

BLOCKED_STATUS = {401, 403, 429, 451}
TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0 (compatible; review-campaign-agent probe)"


@dataclass(frozen=True)
class ProbeResult:
    key: str
    name: str
    domain: str
    verdict: str  # ok | blocked | error
    detail: str


def probe_site(client: httpx.Client, site: Site) -> ProbeResult:
    url = f"https://{site.domain}/"
    try:
        resp = client.get(url, follow_redirects=True)
    except httpx.HTTPError as e:
        return ProbeResult(site.key, site.name, site.domain, "error", type(e).__name__)
    if resp.status_code in BLOCKED_STATUS:
        verdict = "blocked"
    elif resp.status_code >= 400:
        verdict = "error"
    else:
        verdict = "ok"
    return ProbeResult(site.key, site.name, site.domain, verdict, f"HTTP {resp.status_code}")


def probe_sites(sites: list[Site], transport: httpx.BaseTransport | None = None) -> list[ProbeResult]:
    with httpx.Client(transport=transport, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        return [probe_site(client, s) for s in sites]


def format_results(results: list[ProbeResult]) -> str:
    icon = {"ok": "✅", "blocked": "⛔", "error": "⚠️"}
    lines = [f"{icon[r.verdict]} {r.name} ({r.domain}): {r.verdict} - {r.detail}" for r in results]
    counts = {v: sum(r.verdict == v for r in results) for v in icon}
    lines.append(f"합계: 접속 가능 {counts['ok']}, 차단 의심 {counts['blocked']}, 오류 {counts['error']}")
    return "\n".join(lines)
