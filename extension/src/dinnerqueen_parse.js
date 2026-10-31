// 디너의여왕 마이페이지('나의캠페인')의 캠페인 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름은 바뀔 수 있으므로 링크 주소(/taste/번호)와 'N일 남음'·'오늘까지' 같은 문구를 기준으로 읽는다.
export async function scrapeDinnerqueen(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const DDAY_RE = /(\d+)\s*일\s*남음|오늘\s*까지|오늘\s*마감|(\d+)\s*일\s*지남/;

  // 링크 하나가 속한 카드 덩어리를 찾는다: 링크가 하나뿐이면서 마감 문구를 담은 가장 작은 상위 요소.
  function cardFor(a) {
    let el = a;
    while (el && el !== document.body) {
      const text = norm(el.textContent);
      if (DDAY_RE.test(text) && el.querySelectorAll('a[href^="/taste/"]').length === 1) return el;
      el = el.parentElement;
    }
    return a;
  }

  function readCards() {
    const cards = new Map();
    for (const a of document.querySelectorAll('a[href^="/taste/"]')) {
      const href = a.getAttribute("href") || "";
      const id = (href.match(/\/taste\/(\d+)/) || [])[1];
      if (!id) continue;
      if (!cards.has(id)) cards.set(id, { el: cardFor(a), href });
    }
    const out = [];
    for (const [id, { el, href }] of cards) {
      const text = norm(el.textContent);
      let daysLeft = null;
      let m = text.match(/(\d+)\s*일\s*남음/);
      if (m) daysLeft = Number(m[1]);
      else if (/오늘\s*까지|오늘\s*마감/.test(text)) daysLeft = 0;
      else if ((m = text.match(/(\d+)\s*일\s*지남/))) daysLeft = -Number(m[1]);
      // 제목: 카드 안 이미지의 alt(링크 title 은 '신청하기' 꼬리가 붙는다). 없으면 링크 title 에서 꼬리를 떼고 쓴다.
      const img = el.querySelector("img[alt]");
      let title = img ? norm(img.getAttribute("alt")) : "";
      if (!title) title = norm(a.getAttribute("title") || "").replace(/\s*신청하기$/, "");
      // 제공내역: 제목 문단 다음에서, 마감·신청수 문단이 아닌 첫 문단 (제목 앞 배지 문단은 제외).
      const paras = [...el.querySelectorAll("p")].map((p) => norm(p.textContent));
      const titleIdx = paras.findIndex((t) => t && t === title);
      const afterTitle = titleIdx >= 0 ? paras.slice(titleIdx + 1) : paras;
      const provided = afterTitle.find((t) => t && !DDAY_RE.test(t) && !/신청\s*\d+/.test(t)) || "";
      const KINDS = ["릴스", "클립", "랜덤픽", "배송", "기자단", "페이백"];
      const kind = KINDS.find((k) => text.includes(k)) || null;
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
