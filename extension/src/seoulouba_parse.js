// 서울오빠(seoulouba.co.kr)의 캠페인 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름은 바뀔 수 있으므로 링크 주소(/campaign/?c=번호)와 'D-n'·'D-day' 같은 문구를 기준으로 읽는다.
// 2026-11-01 공개 캠페인 목록(https://seoulouba.co.kr/campaign/)의 카드 구조를 기준으로 만들었고,
// 마이페이지('내 캠페인', /mypage/my_campaign.php)도 같은 테마 마크업으로 그려지는 것으로 보나 로그인 화면 실측 전이다.
export async function scrapeSeoulouba(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const DDAY_RE = /D\s*-\s*\d+|D\s*-\s*day|D\s*\+\s*\d+/;
  // 목록 하단의 '더보기' 버튼. 누르면 같은 카드 마크업이 이어 붙는다.
  const moreBtn = () => document.querySelector("#list_more_btn");

  // 링크 하나가 속한 카드 덩어리를 찾는다: 캠페인 링크(상세 주소 ?c=번호)가 하나뿐이면서
  // 마감 문구를 담은 가장 작은 상위 요소.
  function cardFor(a) {
    let el = a;
    while (el && el !== document.body) {
      const text = norm(el.textContent);
      const ids = new Set(
        [...el.querySelectorAll('a[href*="/campaign/?c="]')]
          .map((x) => ((x.getAttribute("href") || "").match(/[?&]c=(\d+)/) || [])[1])
          .filter(Boolean)
      );
      if (DDAY_RE.test(text) && ids.size === 1) return el;
      el = el.parentElement;
    }
    return a;
  }

  function readCards() {
    const cards = new Map();
    for (const a of document.querySelectorAll('a[href*="/campaign/?c="]')) {
      const href = a.getAttribute("href") || "";
      const id = (href.match(/[?&]c=(\d+)/) || [])[1];
      if (!id) continue;
      if (!cards.has(id)) cards.set(id, { el: cardFor(a), href });
    }
    const out = [];
    for (const [id, { el, href }] of cards) {
      const text = norm(el.textContent);
      let daysLeft = null;
      let m = text.match(/D\s*-\s*(\d+)/);
      if (m) daysLeft = Number(m[1]);
      else if (/D\s*-\s*day/i.test(text)) daysLeft = 0;
      else if ((m = text.match(/D\s*\+\s*(\d+)/))) daysLeft = -Number(m[1]);
      const title = norm(el.querySelector(".t_ttl strong, .t_ttl")?.textContent);
      const provided = norm(el.querySelector(".t_basic")?.textContent);
      // 유형: 카드 위쪽 배지 문구(방문형·배송형·기자단·구매평·클립·서비스형…). 복합 유형(블로그+클립)을 먼저 본다.
      const badges = norm(el.querySelector(".icon_tag")?.textContent);
      const KINDS = ["블로그+클립", "리뷰+구매평", "방문형", "배송형", "기자단", "구매평", "클립", "서비스형"];
      const kind = KINDS.find((k) => badges.includes(k) || title.includes(k)) || null;
      out.push({ campaignId: id, title, provided, kind, daysLeft, href });
    }
    return out;
  }

  // '더보기' 방식 목록: 버튼을 눌러야 카드가 이어 붙는다. 버튼이 사라질 때까지 누르고,
  // 버튼이 없는 화면(마이페이지 등)에서는 스크롤만으로 카드 수가 안정될 때까지 기다린다.
  let count = -1;
  let same = 0;
  for (let i = 0; i < maxRounds && same < 2; i++) {
    const btn = moreBtn();
    if (btn) btn.click();
    const now = readCards().length;
    same = now === count && !btn ? same + 1 : 0;
    count = now;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(sleepMs);
  }
  return readCards();
}
