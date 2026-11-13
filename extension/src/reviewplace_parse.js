// 리뷰플레이스 마이페이지('내 캠페인')의 캠페인 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름은 바뀔 수 있으므로 링크 주소(/pr/?id=번호)와 'D-n'·'오늘마감' 같은 문구를 기준으로 읽는다.
export async function scrapeReviewplace(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const DDAY_RE = /D\s*-\s*\d+|오늘\s*마감|D\s*\+\s*\d+/;

  // 링크 하나가 속한 카드 덩어리를 찾는다: 링크가 하나뿐이면서 마감 문구를 담은 가장 작은 상위 요소.
  function cardFor(a) {
    let el = a;
    while (el && el !== document.body) {
      const text = norm(el.textContent);
      if (DDAY_RE.test(text) && el.querySelectorAll('a[href*="/pr/?id="]').length === 1) return el;
      el = el.parentElement;
    }
    return a;
  }

  function readCards() {
    const cards = new Map();
    for (const a of document.querySelectorAll('a[href*="/pr/?id="]')) {
      const rawHref = a.getAttribute("href") || "";
      const id = (rawHref.match(/[?&]id=(\d+)/) || [])[1];
      if (!id) continue;
      const href = rawHref.startsWith("http")
        ? new URL(rawHref).pathname + new URL(rawHref).search
        : rawHref;
      if (!cards.has(id)) cards.set(id, { el: cardFor(a), href });
    }
    const out = [];
    for (const [id, { el, href }] of cards) {
      const text = norm(el.textContent);
      // '신청' 상태(취소 버튼, 선정 마감 대기)이거나 마감일 표기가 없는 카드는 선정된 진행중 캠페인이 아니므로 제외한다
      if (text.includes("취소") || /선정\s*마감|\d+\s*일\s*남음/.test(text)) {
        continue;
      }
      let daysLeft = null;
      let m = text.match(/D\s*-\s*(\d+)/);
      if (m) daysLeft = Number(m[1]);
      else if (/오늘\s*마감/.test(text)) daysLeft = 0;
      else if ((m = text.match(/D\s*\+\s*(\d+)/))) daysLeft = -Number(m[1]);
      if (daysLeft == null) {
        // D-n 표기가 없는 카드는 진행중 캠페인이 아니다
        continue;
      }
      // 제목·제공내역은 문단 순서대로: 첫 문단이 제목, 그 다음이 제공내역(마감·신청수 문단 제외).
      const paras = [...el.querySelectorAll("p")].map((p) => norm(p.textContent)).filter(Boolean);
      const title = paras[0] || "";
      const provided =
        paras.slice(1).find((t) => !DDAY_RE.test(t) && !/신청\s*\d+/.test(t) && t !== title) || "";
      const KINDS = ["구매평", "기자단"];
      const kind = KINDS.find((k) => title.includes(k)) || null;
      out.push({ campaignId: id, title, provided, kind, daysLeft, href });
    }
    return out;
  }

  let count = -1;
  let same = 0;
  for (let i = 0; i < maxRounds && same < 2; i++) {
    const now = readCards().length;
    same = now === count ? same + 1 : 0;
    count = now;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(sleepMs);
  }
  return readCards();
}
