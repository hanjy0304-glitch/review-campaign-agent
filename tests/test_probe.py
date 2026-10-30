import httpx

from review_campaign_agent.catalog import Site
from review_campaign_agent.probe import format_results, probe_sites


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    if host == "ok.example":
        return httpx.Response(200)
    if host == "blocked.example":
        return httpx.Response(403)
    if host == "down.example":
        raise httpx.ConnectTimeout("timeout")
    return httpx.Response(500)


def test_probe_classifies_results():
    sites = [Site(k, k, f"{k}.example") for k in ("ok", "blocked", "down", "broken")]
    results = probe_sites(sites, transport=httpx.MockTransport(_handler))
    assert [r.verdict for r in results] == ["ok", "blocked", "error", "error"]
    assert results[2].detail == "ConnectTimeout"
    assert "접속 가능 1, 차단 의심 1, 오류 2" in format_results(results)
