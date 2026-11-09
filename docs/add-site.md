# 새 체험단 사이트 자동 수집에 추가하기

리뷰노트처럼 다른 체험단 사이트도 자동 수집하려면, 그 사이트의 "내 체험단(진행중)" 화면 구조가 필요합니다.
이 문서는 그 절차를 설명합니다. 수집기(크롬 확장)는 여러 사이트를 이미 지원하도록 되어 있어서,
새 사이트를 추가할 때는 아래 3가지를 만들면 됩니다.

## 왜 화면 구조가 필요한가

- 수집기는 사이트에 로그인한 크롬 화면에서 카드를 읽습니다(사이트마다 화면 생김새가 달라서 파서가 따로 필요합니다).
- 로그인한 화면의 생김새는 밖에서 볼 수 없습니다. 규칙 11(보안 최우선)에 따라 로그인 화면을 대신 열어보는 방법도 없습니다.
- 그래서 **사용자가 자기 PC에서 로그인된 화면의 구조를 캡처해서 알려주면**, 그 결과(개인정보는 가려진 텍스트)를 보고 파서를 만듭니다.

## 절차 (사이트 하나당 한 번)

1. **사용자: 화면 구조 캡처** — `tools/capture.js`를 사용합니다. 자기 PC 크롬에서 그 사이트에 로그인한 뒤,
   "진행중 체험단" 화면을 열고 개발자 콘솔에 붙여 넣어 결과를 복사합니다. 결과에는 카드의 HTML 골격만 남고
   개인정보(아이디, 실제 캠페인 제목 등)는 가려집니다. 자세한 방법은 `tools/capture_bookmarklet.txt` 참고.
2. **익명화 fixture 만들기** — 캡처 결과의 실제 제목·업체명을 가짜 값(`[테스트/가상] 예시 …`)으로 바꿔
   `extension/test/fixtures/<사이트키>.html`로 저장합니다. 원본(개인정보 남은 것)은 저장소에 넣지 않고,
   필요하면 `fixtures_private/`(gitignore)에만 둡니다.
3. **파서 작성** — `extension/src/<사이트키>_parse.js`를 만듭니다. `reviewnote_parse.js`를 예로 삼되
   `#번호`·`D-n`처럼 그 사이트의 실제 형태를 기준으로 읽어야 하고, 클래스 이름(자주 바뀜)에 의존하지 않습니다.
4. **목록에 등록** — `extension/src/sites.js`의 `SITES`에 사이트를 한 줄 추가합니다
   (key·이름·주소·로그인 확인 접두사·파서). manifest.json의 `host_permissions`에 그 사이트 주소를 추가합니다.
5. **확인** — `extension/test/fixtures`의 fixture로 테스트를 돌리고(`cd extension && npm test`),
   실제 화면에서 확장의 `지금 수집`을 눌러 Notion에 행이 만들어지는지 확인합니다.
6. **기록** — `config/sites.yaml`의 그 사이트 칸을 고칩니다: `adapter: experimental`,
   `login_type`(확인된 것만), `my_applications_url`(확장이 여는 주소).

## 서버(GitHub Actions) 수집기로 추가하기

크롬 확장은 사용자 PC가 켜져 있어야 수집합니다. PC 없이도 돌게 하려면 서버 수집기를 하나 더 만듭니다.
사이트가 아이디·비밀번호 로그인을 지원하고, **사용자가 자기 계정을 GitHub Secrets 에 등록하는 데 동의한 경우에만** 진행합니다 (규칙 11의 예외, 사용자가 직접 선택한 경우).

1. **로그인 흐름 확인** — 로그인 페이지의 폼 주소·필드 이름과 로그인 후 "선정된 내역" 주소를 확인해 적습니다.
   비밀번호는 절대 입력해 보지 않고, 공개 페이지에서 폼 구조만 읽습니다.
2. **수집기 작성** — `review_campaign_agent/collectors/<사이트키>.py` 에 `base.Collector` 하위 클래스를 만듭니다.
   로그인 세션(쿠키) 유지, 환경변수 읽기(`<KEY>_ID` / `<KEY>_PW`), 계정 값 미출력은 `base.py` 가 맞습니다.
   파싱은 클래스 이름이 아니라 링크 주소·문구(`D-n`, `오늘마감`)로 카드를 찾습니다 (`reviewplace.py` 참고).
3. **등록** — `review_campaign_agent/collectors/__init__.py` 의 `COLLECTORS` 에 추가합니다.
4. **워크플로우** — 수집을 정해진 시간에 자동으로 돌리려면 `.github/workflows/collect.yml` 에 실행 단계를 둡니다.
   현재 내용은 [collect-workflow.yml](collect-workflow.yml) 에 있고, GitHub App 토큰은 워크플로 파일을 푸시할 권한이 없어서
   사용자가 GitHub 웹에서 그 내용을 `.github/workflows/collect.yml` 로 한 번 저장하는 방식입니다. env 에 `<KEY>_ID` / `<KEY>_PW` 를 넣습니다.
5. **테스트** — `tests/test_collector.py` 처럼 `httpx.MockTransport` 로 로그인 성공·실패·파싱을 검증합니다.
   실제 화면에서 받은 HTML 은 개인정보를 가린 것만 커밋하고, 원본은 `fixtures_private/`(gitignore)에만 둡니다.
6. **확인** — 사용자가 Secrets 를 등록한 뒤 Actions → **체험단 서버 수집** → **Run workflow** 로 먼저 확인합니다(기본값 `확인만`, 표에 저장하지 않음). 로그에 사이트별로 `N건 확인`/`건너뜀`/`실패`가 한 줄씩 나옵니다.

## 다음 후보 (2026-11-09 기준)

- **강남맛집은 파서가 등록돼 있습니다** (`extension/src/gangnam_parse.js`). 2026-11-06 공개 캠페인 목록
  (https://강남맛집.net/cp/) 의 카드 구조(`li.list_item` · `#c_box ul li` 안의 `.textArea`)를 기준으로 만들었고,
  마이페이지(`/theme/go/mypage/`)도 같은 카드 스킨(`#c_box ul li .textArea`)을 쓰는 것을 테마 CSS로 확인했습니다.
  다만 로그인한 마이페이지 화면은 아직 실측 전이라, PC에서 확장의 `지금 수집`을 한 번 돌려 행이 만들어지는지
  확인해야 합니다. 이상이 있으면 로그인 화면 캡처(`tools/capture.js`) 결과로 고치면 됩니다.
  주의: `gangnam-review.net` 은 강남맛집.net(punycode `xn--939au0g4vj8sq.net`)으로 301 리다이렉트되므로
  `sites.js` 에는 리다이렉트 뒤 주소를 적어야 로그인 확인(`loggedInPrefix`)이 통과합니다.
- **디너의여왕·리뷰플레이스는 파서가 등록돼 있습니다** (`extension/src/dinnerqueen_parse.js`,
  `extension/src/reviewplace_parse.js`). 다만 공개 캠페인 목록 화면의 카드 구조를 기준으로 만든 것이라,
  로그인된 마이페이지에서 확장의 `지금 수집`을 한 번 돌려 실제로 행이 만들어지는지 확인해야 합니다.
  확인 전이라도 이상이 있으면 로그인 화면 캡처(tools/capture.js) 결과로 고치면 됩니다.
- **서울오빠는 파서가 등록돼 있습니다** (`extension/src/seoulouba_parse.js`). 공개 캠페인 목록
  (https://seoulouba.co.kr/campaign/) 의 카드 구조를 기준으로 만든 것이라, 로그인된
  마이페이지('내 캠페인')에서 확장의 `지금 수집`을 한 번 돌려 실제로 행이 만들어지는지 확인해야 합니다.
  확인 전이라도 이상이 있으면 로그인 화면 캡처(tools/capture.js) 결과로 고치면 됩니다.
- **포포몬은 파서가 등록돼 있습니다** (`extension/src/popomon_parse.js`). 2026-11-09 공개 캠페인 카드 구조
  (https://popomon.com/) 와 마이페이지(/next/mypage)를 기준으로 만들었습니다.
- **서버 수집기(2026-11-09, PR 발행)**: 강남맛집·디너의여왕·리뷰플레이스·포포몬·서울오빠 5곳.
  `review_campaign_agent/collectors/<사이트키>.py`. 로그인 경로와 실패 응답은 실제 사이트에서 확인했지만,
  계정으로 로그인한 뒤의 목록 응답은 아직 실측 전입니다(Secrets 등록 후 `확인만` 실행으로 확인).
- **리뷰노트는 서버 수집을 붙이지 않았습니다.** `/sns/login` 은 네이버·Apple 버튼만 있고,
  `/users/login` 의 이메일·비밀번호 로그인은 Firebase(`reviewnote-e92d9`) 인증 뒤 앱 토큰을 한 번 더
  교환하는 2단계라, 네이버로 가입한 계정에는 쓸 비밀번호가 없습니다. 리뷰노트는 크롬 확장이 계속 담당합니다.
- 그 외 미구현 사이트: 미블, 체험뷰, 아싸뷰, 슈퍼멤버스, 레뷰, 클라우드리뷰, 티블, 놀러와, 링블, 어디야체험단, 리워딩스, 스타일씨.
  로그인 방식은 `config/sites.yaml`에 기록된 것을 참고하세요.
