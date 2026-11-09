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

## 다음 후보 (2026-11-06 기준)

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
- 그 외 미구현 사이트: 미블, 체험뷰, 아싸뷰, 슈퍼멤버스.
  로그인 방식은 `config/sites.yaml`에 기록된 것을 참고하세요.
