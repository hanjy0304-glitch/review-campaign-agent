// 포포몬(popomon.com) 마이페이지의 캠페인 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름은 바뀔 수 있으므로 링크 주소(/next/campaign/번호)와 'D-n'·'n일 남음'·'오늘 마감' 같은 문구를 기준으로 읽는다.
// 2026-11-09 공개 캠페인 카드 구조(https://popomon.com/)를 기준으로 만들었다.
export async function scrapePopomon(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const now = options.now instanceof Date ? options.now : new Date();
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const DDAY_RE = /D\s*-\s*\d+|D\s*-?\s*day|D\s*\+\s*\d+|\d+\s*일\s*남음|오늘\s*(?:마감|까지)|\d+\s*일\s*지남|~\s*\d{1,2}\s*[./]\s*\d{1,2}|\d{1,2}\s*[./]\s*\d{1,2}\s*(?:까지|마감)/i;

  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const todayUtc = Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate());

  function daysUntil(month, day) {
    if (!(month >= 1 && month <= 12) || !(day >= 1 && day <= 31)) return null;
    let target = Date.UTC(kst.getUTCFullYear(), month - 1, day);
    if (target < todayUtc - 183 * 86400000) target = Date.UTC(kst.getUTCFullYear() + 1, month - 1, day);
    const diff = Math.round((target - todayUtc) / 86400000);
    return Number.isFinite(diff) ? diff : null;
  }

  function readDays(text) {
    let m = text.match(/D\s*-\s*(\d+)/i);
    if (m) return Number(m[1]);
    if (/D\s*-?\s*day/i.test(text)) return 0;
    if ((m = text.match(/(\d+)\s*일\s*남음/))) return Number(m[1]);
    if (/오늘\s*(?:마감|까지)/.test(text)) return 0;
    if ((m = text.match(/(\d+)\s*일\s*지남/))) return -Number(m[1]);
    if ((m = text.match(/D\s*\+\s*(\d+)/i))) return -Number(m[1]);
    if ((m = text.match(/~\s*(\d{1,2})\s*[./]\s*(\d{1,2})/))) return daysUntil(Number(m[1]), Number(m[2]));
    if ((m = text.match(/(\d{1,2})\s*[./]\s*(\d{1,2})\s*(?:까지|마감)/))) return daysUntil(Number(m[1]), Number(m[2]));
    return null;
  }

  function cardFor(a) {
    let el = a;
    let fallback = null;
    while (el && el !== document.body) {
      const ids = new Set(
        [...el.querySelectorAll('a[href*="/campaign/"]')]
          .map((x) => (x.getAttribute("href") || "").match(/(?:campaign\/|[?&]id=)(\d+)/)?.[1])
          .filter(Boolean)
      );
      if (ids.size === 1) {
        fallback = el;
        if (DDAY_RE.test(norm(el.textContent))) return el;
      } else if (ids.size > 1) {
        break;
      }
      el = el.parentElement;
    }
    return fallback || a;
  }

  function readCards() {
    const cards = new Map();
    for (const a of document.querySelectorAll('a[href*="/campaign/"]')) {
      const rawHref = a.getAttribute("href") || "";
      const m = rawHref.match(/(?:campaign\/|[?&]id=)(\d+)/);
      if (!m) continue;
      const id = m[1];
      const path = rawHref.startsWith("http") ? new URL(rawHref).pathname : rawHref;
      if (!cards.has(id)) cards.set(id, { el: cardFor(a), href: path });
    }
    const out = [];
    for (const [id, { el, href }] of cards) {
      const text = norm(el.textContent);
      const daysLeft = readDays(text);

      const heading = el.querySelector("h3, h4, strong");
      let title = norm(heading ? heading.textContent : "");
      if (!title) {
        const lines = (el.innerText || el.textContent || "")
          .split("\n")
          .map((s) => norm(s))
          .filter(Boolean);
        const titleLine = lines.find((l) => /^\[.*?\]/.test(l)) || lines[0] || "";
        title = titleLine;
      }

      let provided = "";
      const allLines = (el.innerText || el.textContent || "")
        .split("\n")
        .map((s) => norm(s))
        .filter(Boolean);
      const provLine = allLines.find(
        (l) => l !== title && (l.includes("상당의") || l.includes("제공") || l.includes("이용권") || l.includes("식사권"))
      );
      if (provLine) provided = provLine;

      let kind = null;
      if (text.includes("방문형") || text.includes("방문")) kind = "방문형";
      else if (text.includes("배송형") || text.includes("배송")) kind = "배송형";
      else if (text.includes("기자단")) kind = "기자단";
      else if (text.includes("구매형")) kind = "구매평";

      out.push({ campaignId: id, title, provided, kind, daysLeft, href });
    }
    return out;
  }

  let count = -1;
  let same = 0;
  for (let i = 0; i < maxRounds && same < 2; i++) {
    const nowCount = readCards().length;
    same = nowCount === count ? same + 1 : 0;
    count = nowCount;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(sleepMs);
  }
  return readCards();
}
