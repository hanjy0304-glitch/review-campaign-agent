"""체험단 관리 Notion DB 양식.

사람이 입력하는 칸과 에이전트가 관리하는 칸을 나눴다. 에이전트는 '사람 칸'을 덮어쓰지 않는다.

사람 칸:     유형, 진행단계, 방문일, 페이백, 제공내역, 방문가능시간, 메모
              (수동 입력 행은 체험단명, 사이트, 글마감일도 직접 입력)
에이전트 칸: 선정상태, 선정일, 남은일수, 입력방식, 고유키, 알림이력, (자동 수집 시 글마감일·링크)
"""

TITLE = "체험단명"
SITE = "사이트"
KIND = "유형"
SELECTION = "선정상태"
STAGE = "진행단계"
DEADLINE = "글마감일"
VISIT = "방문일"
DAYS_LEFT = "남은일수"
PAYBACK = "페이백"
PROVIDED = "제공내역"
VISIT_TIME = "방문가능시간"
SELECTED_AT = "선정일"
URL = "링크"
MEMO = "메모"
SOURCE = "입력방식"
KEY = "고유키"
NOTIFIED = "알림이력"

KINDS = ["방문형", "배송형", "구매평", "기자단", "기타"]
SELECTION_STATES = ["신청", "선정", "탈락"]
STAGES = ["진행필요", "예약완료", "체험완료", "작성완료"]
PAYBACK_STATES = ["해당없음", "필요", "완료"]
SOURCES = ["자동", "수동"]

SELECTED_STATE = "선정"
REJECTED_STATE = "탈락"
APPLIED_STATE = "신청"
STAGE_NEED = "진행필요"
STAGE_VISITED = "체험완료"
STAGE_DONE = "작성완료"
SOURCE_AUTO = "자동"
SOURCE_MANUAL = "수동"
OTHER_SITE = "기타"


def _select(options: list[str]) -> dict:
    return {"select": {"options": [{"name": n} for n in options]}}


def database_properties(site_names: list[str]) -> dict:
    """Notion 데이터베이스 생성용 속성 정의 (표시 순서는 Notion 에서 자유롭게 바꿔도 된다)."""
    sites = list(dict.fromkeys([*site_names, OTHER_SITE]))
    return {
        TITLE: {"title": {}},
        SITE: _select(sites),
        KIND: _select(KINDS),
        STAGE: _select(STAGES),
        DEADLINE: {"date": {}},
        DAYS_LEFT: {"number": {"format": "number"}},
        VISIT: {"date": {}},
        VISIT_TIME: {"rich_text": {}},
        PROVIDED: {"rich_text": {}},
        PAYBACK: _select(PAYBACK_STATES),
        SELECTION: _select(SELECTION_STATES),
        SELECTED_AT: {"date": {}},
        URL: {"url": {}},
        MEMO: {"rich_text": {}},
        SOURCE: _select(SOURCES),
        KEY: {"rich_text": {}},
        NOTIFIED: {"rich_text": {}},
    }
