"""전 사이트 서버 수집기 테스트 (MockTransport).

실제 사이트에 로그인해 보지 않고, 각 사이트가 돌려주는 화면·응답의 **골격**을 흉내 내 검증한다.
fixture 의 카드 구조는 공개 페이지에서 확인한 마크업을 값만 가상으로 바꾼 것이다.
계정 정보는 모두 가상 값이며, 오류 메시지에 섞이지 않는지도 함께 확인한다.
"""

from datetime import date

import httpx
import pytest

from review_campaign_agent.catalog import Site, load_catalog
from review_campaign_agent.collectors import COLLECTORS, ERROR, OK, SKIPPED, collect_sites
from review_campaign_agent.collectors.base import LoginError
from review_campaign_agent.collectors.common import days_left, normalize_kind
from review_campaign_agent.collectors.dinnerqueen import DinnerqueenCollector
from review_campaign_agent.collectors.dinnerqueen import parse_campaigns as parse_dinnerqueen
from review_campaign_agent.collectors.gangnam import GangnamCollector
from review_campaign_agent.collectors.gangnam import parse_campaigns as parse_gangnam
from review_campaign_agent.collectors.popomon import PopomonCollector
from review_campaign_agent.collectors.popomon import parse_campaigns as parse_popomon
from review_campaign_agent.collectors.seoulouba import SeouloubaCollector
from review_campaign_agent.collectors.seoulouba import parse_campaigns as parse_seoulouba
from review_campaign_agent.models import Status

TODAY = date(2026, 11, 9)
ID_VALUE = "가상아이디"
CRED_VALUE = "가상비밀번호"


# ─── 공통 ────────────────────────────────────────────────────────────────────


def client_for(handler, origin: str) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=origin, follow_redirects=True)


def test_all_collectors_are_registered():
    assert {"gangnam", "dinnerqueen", "reviewplace", "popomon", "seoulouba"} <= set(COLLECTORS)
    for key, cls in COLLECTORS.items():
        assert cls.key == key and cls.name and cls.origin.startswith("https://")


def test_collect_sites_skips_sites_without_credentials():
    reports = collect_sites(load_catalog(), {}, TODAY)
    assert {r.key for r in reports} == {"gangnam", "dinnerqueen", "reviewplace", "popomon", "seoulouba"}
    assert all(r.status == SKIPPED for r in reports)


def test_days_left_reads_every_site_style():
    assert days_left("D-7") == 7
    assert days_left("D-day") == 0
    assert days_left("24일 남음") == 24
    assert days_left("오늘까지") == 0
    assert days_left("3일 지남") == -3
    assert days_left("D+4") == -4
    assert days_left("11.11 까지", TODAY) == 2
    assert days_left("11.05 ~ 11.11", TODAY) == 2
    assert days_left("1.3 까지", TODAY) == 55  # 연도가 없으면 가까운 쪽(내년)으로 읽는다
    assert days_left("마감", TODAY) is None


def test_normalize_kind_keeps_only_notion_options():
    assert normalize_kind("방문형") == "방문형"
    assert normalize_kind("배송") == "배송형"
    assert normalize_kind("[블로그+클립] 기자단 모집") == "기자단"
    assert normalize_kind("리뷰+구매평") == "구매평"
    assert normalize_kind("릴스 랜덤픽") is None


def test_collect_sites_continues_after_a_failure():
    """한 사이트가 실패해도 다음 사이트를 계속 돈다 (전 사이트 등록 뒤에도 같은 규칙이 지켜지는지)."""
    sites = [
        Site("popomon", "포포몬", "popomon.com"),
        Site("dinnerqueen", "디너의여왕", "dinnerqueen.net"),
        Site("seoulouba", "서울오빠", "seoulouba.co.kr"),
    ]
    env = {
        "POPOMON_ID": "u",
        "POPOMON_PW": "p",
        "DINNERQUEEN_ID": "u",
        "DINNERQUEEN_PW": "p",
        "SEOULOUBA_ID": "u",
        "SEOULOUBA_PW": "p",
    }
    clients = {
        "popomon": client_for(FakePopomon(), PopomonCollector.origin),
        "dinnerqueen": client_for(FakeDinnerqueen(password_error=True), DinnerqueenCollector.origin),
        "seoulouba": client_for(FakeSeoulouba(), SeouloubaCollector.origin),
    }
    reports = collect_sites(sites, env, TODAY, client_factory=lambda cls: clients[cls.key])

    assert [r.status for r in reports] == [OK, ERROR, OK]
    assert reports[0].count == 7
    assert reports[2].count == 2


# ─── 서울오빠 (그누보드) ─────────────────────────────────────────────────────

SEOULOUBA_LIST = """
<ul class="campaign_wbox">
  <li class="campaign_content">
    <div class="load_campaign">
      <a href="https://seoulouba.co.kr/campaign/?c=100001" class="tum_img"><img src="/thumb_a.jpg"></a>
      <div class="load_info">
        <div class="icon_tag"><span>방문형</span></div>
        <div class="t_ttl"><a href="https://seoulouba.co.kr/campaign/?c=100001"><strong class="s_campaign_title">[가상] 서울오빠 캠페인 하나</strong></a></div>
        <div class="t_basic"><span class="basic_blue">가상 제공 내역 하나</span></div>
        <div class="campaign_day_people">
          <div class="d_day"><span>D-3</span></div>
          <div class="recruit"><span>신청 5 <span class="span_gray">/ 모집 2</span></span></div>
        </div>
      </div>
    </div>
  </li>
  <li class="campaign_content">
    <div class="load_campaign">
      <a href="https://seoulouba.co.kr/campaign/?c=100002" class="tum_img"><img src="/thumb_b.jpg"></a>
      <div class="load_info">
        <div class="icon_tag"><span>배송형</span></div>
        <div class="t_ttl"><a href="https://seoulouba.co.kr/campaign/?c=100002"><strong class="s_campaign_title">[가상] 서울오빠 캠페인 둘</strong></a></div>
        <div class="t_basic"><span class="basic_blue">가상 제공 내역 둘</span></div>
        <div class="campaign_day_people"><div class="d_day"><span>오늘까지</span></div></div>
      </div>
    </div>
  </li>
  <li class="campaign_content"><a href="/campaign/?c=100001"><p>같은 캠페인을 가리키는 두 번째 링크</p></a></li>
</ul>
<p><a href="/faq.php">자주하는 질문</a></p>
"""

SEOULOUBA_GATE = '<div class="qz-alert">다음 항목에 오류가 있습니다. 로그인 하십시오. <a href="/bbs/login.php">돌아가기</a></div>'


class FakeSeoulouba:
    def __init__(self, gate: bool = False):
        self.gate = gate
        self.login_body = ""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/bbs/login.php":
            return httpx.Response(200, text='<form name="flogin" method="post"><input name="mb_password"></form>',
                                  headers={"set-cookie": "PHPSESSID=sess_so; Path=/"})
        if path == "/bbs/login_check.php":
            self.login_body = request.content.decode()
            return httpx.Response(200, text="<html>login check</html>")
        if path == "/mypage/my_campaign.php":
            return httpx.Response(200, text=SEOULOUBA_GATE if self.gate else SEOULOUBA_LIST)
        return httpx.Response(404)


def test_seoulouba_parse_reads_cards():
    campaigns = parse_seoulouba(SEOULOUBA_LIST, TODAY)
    assert [c.campaign_id for c in campaigns] == ["100001", "100002"]

    first = campaigns[0]
    assert first.title == "[가상] 서울오빠 캠페인 하나"
    assert first.kind == "방문형"
    assert first.status is Status.SELECTED
    assert first.review_deadline.isoformat() == "2026-11-12"  # D-3
    assert first.url == "https://seoulouba.co.kr/campaign/?c=100001"
    assert first.site_name == "서울오빠"

    assert campaigns[1].kind == "배송형"
    assert campaigns[1].review_deadline.isoformat() == TODAY.isoformat()  # 오늘까지


def test_seoulouba_login_and_collect():
    fake = FakeSeoulouba()
    campaigns = SeouloubaCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, SeouloubaCollector.origin))
    assert [c.campaign_id for c in campaigns] == ["100001", "100002"]
    assert "mb_id=%EA%B0%80%EC%83%81%EC%95%84%EC%9D%B4%EB%94%94" in fake.login_body  # 가상아이디
    assert "mb_password=%EA%B0%80%EC%83%81%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8" in fake.login_body
    assert "auto_login=1" in fake.login_body


def test_seoulouba_login_failure_raises_without_leaking_credentials():
    fake = FakeSeoulouba(gate=True)
    with pytest.raises(LoginError) as exc:
        SeouloubaCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, SeouloubaCollector.origin))
    message = str(exc.value)
    assert "로그인에 실패" in message
    assert CRED_VALUE not in message and ID_VALUE not in message


# ─── 강남맛집 (그누보드) ─────────────────────────────────────────────────────

GANGNAM_LIST = """
<div id="c_box"><ul>
  <li>
    <dl>
      <dt class="tit"><a href="/cp/?id=200001">[가상] 강남맛집 캠페인 하나</a></dt>
      <dd class="sub_tit">가상 제공 내역 하나</dd>
    </dl>
    <em class="type">방문형</em>
    <div class="date">24일 남음</div>
    <div class="num">신청 12 / 3명</div>
  </li>
  <li>
    <a href="https://xn--939au0g4vj8sq.net/cp/?id=200002"><img src="/thumb.jpg" alt="[가상] 강남맛집 캠페인 둘"></a>
    <p>가상 제공 내역 둘</p>
    <div class="date">11.11 까지</div>
  </li>
  <li data-product="200003">
    <div class="textArea">
      <div class="tit">[가상] 강남맛집 캠페인 셋</div>
      <p>배송형</p>
      <span>D-1</span>
    </div>
  </li>
</ul></div>
"""

GANGNAM_GATE = """
<script>alert("로그인 한 회원만 접근 가능합니다.");</script>
<form name="flogin" action="/bbs/login_check.php" method="post">
  <input type="text" name="mb_id"><input type="password" name="mb_password">
</form>
"""


class FakeGangnam:
    def __init__(self, gate: bool = False):
        self.gate = gate
        self.login_body = ""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/bbs/login.php":
            return httpx.Response(200, text='<form method="post"><input name="mb_password"></form>',
                                  headers={"set-cookie": "PHPSESSID=sess_gn; Path=/"})
        if path == "/bbs/login_check.php":
            self.login_body = request.content.decode()
            return httpx.Response(200, text="<html>login check</html>")
        if path == "/theme/go/mypage/":
            return httpx.Response(200, text=GANGNAM_GATE if self.gate else GANGNAM_LIST)
        return httpx.Response(404)


def test_gangnam_parse_reads_cards_and_data_product():
    campaigns = parse_gangnam(GANGNAM_LIST, TODAY)
    by_id = {c.campaign_id: c for c in campaigns}
    assert set(by_id) == {"200001", "200002", "200003"}

    first = by_id["200001"]
    assert first.title == "[가상] 강남맛집 캠페인 하나"
    assert first.kind == "방문형"
    assert first.review_deadline.isoformat() == "2026-12-03"  # 24일 남음
    assert first.url == "https://xn--939au0g4vj8sq.net/cp/?id=200001"

    assert by_id["200002"].title == "[가상] 강남맛집 캠페인 둘"  # 제목 클래스가 없으면 이미지 alt
    assert by_id["200002"].review_deadline.isoformat() == "2026-11-11"  # 11.11 까지
    assert by_id["200003"].title == "[가상] 강남맛집 캠페인 셋"  # data-product 카드
    assert by_id["200003"].kind == "배송형"
    assert by_id["200003"].url.endswith("/cp/?id=200003")


def test_gangnam_login_failure_raises_without_leaking_credentials():
    fake = FakeGangnam(gate=True)
    with pytest.raises(LoginError) as exc:
        GangnamCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, GangnamCollector.origin))
    assert "로그인에 실패" in str(exc.value)
    assert CRED_VALUE not in str(exc.value)


# ─── 디너의여왕 (JSON 로그인) ───────────────────────────────────────────────

DINNERQUEEN_LIST = """
<div id="taste_list">
  <div class="qz-dq-card campaign">
    <a class="qz-dq-card__link" href="/taste/300001" title="[가상] 디너의여왕 캠페인 하나 신청하기">
      <div class="qz-dq-card__link__img"><img alt="[가상] 디너의여왕 캠페인 하나" src="/a.jpg"></div>
      <div class="qz-dq-card__badge-row"><span class="qz-dq-badge">배송</span></div>
    </a>
    <div class="qz-dq-card__text">
      <p class="qz-body2-kr">[가상] 디너의여왕 캠페인 하나</p>
      <p class="qz-caption-kr">가상 제공 내역 하나</p>
      <div class="qz-dq-card__stats">
        <p class="dday"><strong>6일 남음</strong></p>
        <p class="apply_badge"><strong>신청 12</strong></p>
      </div>
    </div>
  </div>
  <div class="qz-dq-card campaign">
    <a class="qz-dq-card__link" href="https://dinnerqueen.net/taste/300002" title="[가상] 디너의여왕 캠페인 둘 신청하기">
      <div class="qz-dq-card__link__img"><img alt="[가상] 디너의여왕 캠페인 둘" src="/b.jpg"></div>
    </a>
    <div class="qz-dq-card__text">
      <p class="qz-body2-kr">[가상] 디너의여왕 캠페인 둘</p>
      <p class="dday"><strong>오늘까지</strong></p>
    </div>
  </div>
  <div class="swiper-slide">
    <a href="/taste/999999" title="캐러셀 링크"><img alt="https://img.example.com/banner.jpg" src="/banner.jpg"></a>
  </div>
</div>
"""


class FakeDinnerqueen:
    def __init__(self, password_error: bool = False, redirect_to_main: bool = False):
        self.password_error = password_error
        self.redirect_to_main = redirect_to_main
        self.login_body = ""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login/form_new":
            return httpx.Response(200, text='<form name="login_form"></form>',
                                  headers={"set-cookie": "dq_sessions=sess_dq; Path=/"})
        if path == "/login/proc":
            self.login_body = request.content.decode()
            code = 500 if self.password_error else 200
            return httpx.Response(200, json={"code": code, "msg": "가상 응답"})
        if path == "/mypage/widget":
            if self.redirect_to_main:
                return httpx.Response(302, headers={"location": "/"})
            return httpx.Response(200, text=DINNERQUEEN_LIST)
        if path == "/":
            return httpx.Response(200, text="<html>메인</html>")
        return httpx.Response(404)


def test_dinnerqueen_parse_reads_cards_and_skips_banner_links():
    campaigns = parse_dinnerqueen(DINNERQUEEN_LIST, TODAY)
    assert [c.campaign_id for c in campaigns] == ["300001", "300002"]

    first = campaigns[0]
    assert first.title == "[가상] 디너의여왕 캠페인 하나"
    assert first.kind == "배송형"  # 배지의 '배송'
    assert first.review_deadline.isoformat() == "2026-11-15"  # 6일 남음
    assert first.url == "https://dinnerqueen.net/taste/300001"

    assert campaigns[1].review_deadline.isoformat() == TODAY.isoformat()  # 오늘까지


def test_dinnerqueen_login_and_collect():
    fake = FakeDinnerqueen()
    campaigns = DinnerqueenCollector("가상@example.com", CRED_VALUE).collect(
        TODAY, client=client_for(fake, DinnerqueenCollector.origin)
    )
    assert [c.campaign_id for c in campaigns] == ["300001", "300002"]
    assert "email=%EA%B0%80%EC%83%81%40example.com" in fake.login_body
    assert "gubun=login" in fake.login_body and "snstype=0" in fake.login_body


def test_dinnerqueen_wrong_password_raises_without_leaking_credentials():
    fake = FakeDinnerqueen(password_error=True)
    with pytest.raises(LoginError) as exc:
        DinnerqueenCollector("가상@example.com", CRED_VALUE).collect(
            TODAY, client=client_for(fake, DinnerqueenCollector.origin)
        )
    message = str(exc.value)
    assert "응답 코드 500" in message
    assert CRED_VALUE not in message


def test_dinnerqueen_redirect_to_main_means_not_logged_in():
    fake = FakeDinnerqueen(redirect_to_main=True)
    with pytest.raises(LoginError):
        DinnerqueenCollector("가상@example.com", CRED_VALUE).collect(
            TODAY, client=client_for(fake, DinnerqueenCollector.origin)
        )


# ─── 포포몬 (NextAuth + JSON 목록) ───────────────────────────────────────────

POPOMON_ITEMS = [
    {
        "C_idx": 900001,
        "C_title": "[가상] 포포몬 배송 캠페인",
        "CV_state": "CHOICE",
        "progress_state_ko": "선정 완료",
        "C_recruit_type": "shipping",
        "CV_c_end_date": "2026-11-16",
        "C_regi_end_date": "2026-11-10",
    },
    {
        "C_idx": 900002,
        "C_title": "[가상] 포포몬 방문 캠페인",
        "CV_state": "CHOICE",
        "progress_state_ko": "방문 예정",
        "C_recruit_type": "visiting",
        "CV_c_end_date": "2026-11-13 23:59:59",
    },
    {
        "C_idx": "900003",
        "C_title": "[가상] 마감일 없는 캠페인",
        "CV_state": "CHOICE",
        "C_recruit_type": "ETC",
        "CV_c_end_date": "0000-00-00",
        "CV_request_deadline": "",
    },
]


class FakePopomon:
    """첫 묶음 6건, 다음 묶음 1건 → 두 번 요청하고 끝나는지 확인할 수 있게 한다."""

    def __init__(self, login_fails: bool = False, code_401: bool = False):
        self.login_fails = login_fails
        self.code_401 = code_401
        self.requests: list[httpx.Request] = []
        self.pages: list[str] = []

    def _page_items(self, page: int) -> list[dict]:
        if page == 0:
            extra = [dict(POPOMON_ITEMS[0], C_idx=910000 + i, C_title=f"[가상] 포포몬 캠페인 {i}") for i in range(3)]
            return POPOMON_ITEMS + extra  # 6건
        if page == 1:
            return [dict(POPOMON_ITEMS[1], C_idx=920001, C_title="[가상] 포포몬 캠페인 마지막")]
        return []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/next/api/auth/csrf":
            return httpx.Response(200, json={"csrfToken": "csrf-가상"},
                                  headers={"set-cookie": "__Host-next-auth.csrf-token=csrf; Path=/; Secure"})
        if path == "/next/api/auth/callback/Credentials":
            self.login_body = request.content.decode()
            if self.login_fails:
                return httpx.Response(401, json={"url": "https://popomon.com/next/api/auth/error?error=x"})
            return httpx.Response(200, json={"url": "https://popomon.com/next/mypage"},
                                  headers={"set-cookie": "__Secure-next-auth.session-token=sess_pop; Path=/; Secure"})
        if path == "/next/api/auth/session":
            if self.login_fails:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"user": {"name": "가상"}, "expires": "2026-12-09T00:00:00.000Z"})
        if path == "/api_p/myCampaign/fetch_getContents":
            page = int(dict(request.url.params).get("pageNum", "0"))
            self.pages.append(request.url.params.get("pageNum"))
            if self.code_401:
                return httpx.Response(200, json={"code": 401, "success": False, "message": "로그인 정보가 없습니다."})
            return httpx.Response(200, json={"code": 200, "success": True, "data": {"contentsData1": self._page_items(page)}})
        return httpx.Response(404)


def test_popomon_parse_reads_json_items():
    campaigns = parse_popomon({"data": {"contentsData1": POPOMON_ITEMS}}, TODAY)
    assert [c.campaign_id for c in campaigns] == ["900001", "900002", "900003"]

    first = campaigns[0]
    assert first.title == "[가상] 포포몬 배송 캠페인"
    assert first.kind == "배송형"
    assert first.review_deadline.isoformat() == "2026-11-16"  # CV_c_end_date(제출기간)
    assert first.url == "https://popomon.com/next/campaign/900001"
    assert first.site_name == "포포몬"

    assert campaigns[1].kind == "방문형"
    assert campaigns[1].review_deadline.isoformat() == "2026-11-13"
    assert campaigns[2].review_deadline is None  # 0000-00-00 은 날짜가 아니다


def test_popomon_login_pages_through_the_list():
    fake = FakePopomon()
    campaigns = PopomonCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, PopomonCollector.origin))

    assert fake.pages == ["0", "1"]  # 한 묶음이 6건이면 다음 쪽을 더 읽는다
    assert len(campaigns) == 7
    assert len({c.campaign_id for c in campaigns}) == 7
    assert "username=%EA%B0%80%EC%83%81%EC%95%84%EC%9D%B4%EB%94%94" in fake.login_body
    assert "password=%EA%B0%80%EC%83%81%EB%B9%84%EB%B0%80%EB%B2%88%ED%98%B8" in fake.login_body
    assert "state=choice" in str(fake.requests[-1].url)


def test_popomon_login_failure_raises_without_leaking_credentials():
    fake = FakePopomon(login_fails=True)
    with pytest.raises(LoginError) as exc:
        PopomonCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, PopomonCollector.origin))
    message = str(exc.value)
    assert "로그인에 실패" in message
    assert CRED_VALUE not in message and ID_VALUE not in message


def test_popomon_list_login_required_becomes_login_error():
    fake = FakePopomon(code_401=True)
    with pytest.raises(LoginError):
        PopomonCollector(ID_VALUE, CRED_VALUE).collect(TODAY, client=client_for(fake, PopomonCollector.origin))
