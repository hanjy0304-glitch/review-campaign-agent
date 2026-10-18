// 리뷰노트 '내 체험단 > 진행중' 화면의 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름(Tailwind)은 자주 바뀌므로 링크 주소(/campaigns/…), '#번호', 'D-n' 같은 형태를 기준으로 읽는다.
export async function scrapeReviewnote(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const KINDS = ["방문형", "배송형", "구매평", "기자단"];
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function readCards() {
    const cards = new Map();
    for (const a of document.querySelectorAll('a[href^="/campaigns/"]')) {
      let el = a;
      let id = null;
      while (el && el !== document.body) {
        const m = norm(el.textContent).match(/#(\d{4,})/);
        if (m) {
          id = m[1];
          break;
        }
        el = el.parentElement;
      }
      if (!id) continue;
      if (!cards.has(id)) cards.set(id, { el, anchors: [] });
      cards.get(id).anchors.push(a);
    }
    const out = [];
    for (const [id, { el, anchors }] of cards) {
      const text = norm(el.textContent);
      let daysLeft = null;
      let m = text.match(/D\s*-\s*(\d+)/);
      if (m) daysLeft = Number(m[1]);
      else if (/D\s*-\s*day/i.test(text)) daysLeft = 0;
      else if ((m = text.match(/D\s*\+\s*(\d+)/))) daysLeft = -Number(m[1]);
      const titleAnchor = anchors.find((a) => norm(a.textContent) && !/D\s*[-+]/.test(norm(a.textContent)));
      const title = norm(titleAnchor ? titleAnchor.textContent : "");
      const provided = norm((el.querySelector(".truncate") || {}).textContent);
      out.push({
        campaignId: id,
        title,
        provided,
        kind: KINDS.find((k) => text.includes(k)) || null,
        daysLeft,
        href: anchors[0].getAttribute("href"),
      });
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
