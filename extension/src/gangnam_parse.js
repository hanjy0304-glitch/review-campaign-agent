// 강남맛집(gangnam-review.net → 강남맛집.net, punycode xn--939au0g4vj8sq.net) 마이페이지의 캠페인 카드를 읽는다.
// executeScript 의 func 로 페이지에 주입되므로 바깥 변수·import 에 의존하지 않는 하나의 함수로 둔다.
// 클래스 이름은 바뀔 수 있으므로 링크 주소(/cp/?id=번호)와 '24일 남음'·'D-n'·'11.11 까지' 같은 마감 문구를 기준으로 읽는다.
// 2026-11-06 공개 캠페인 목록(https://xn--939au0g4vj8sq.net/cp/)과 마이페이지 CSS(#c_box ul li .textArea)의
// 카드 구조를 기준으로 만들었고, 로그인한 마이페이지(/theme/go/mypage/)의 실제 화면은 아직 실측 전이다.
export async function scrapeGangnam(options = {}) {
  const sleepMs = options.sleepMs ?? 800;
  const maxRounds = options.maxRounds ?? 20;
  const now = options.now instanceof Date ? options.now : new Date();
  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const DDAY_RE = /D\s*-\s*\d+|D\s*-?\s*day|D\s*\+\s*\d+|\d+\s*일\s*남음|오늘\s*(?:마감|까지)|\d+\s*일\s*지남|~\s*\d{1,2}\s*[./]\s*\d{1,2}|\d{1,2}\s*[./]\s*\d{1,2}\s*(?:까지|마감)/i;
  const ID_RE = /[?&]id=(\d+)/;

  // 한국시간(KST) 기준 오늘 자정을 UTC 밀리초로. 서버·PC 시간대와 무관하게 같은 날짜를 쓰기 위해서다.
  const kst = new Date(now.getTime() + 9 * 3600 * 1000);
  const todayUtc = Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate());

  // '11.11 까지' 처럼 날짜로 적힌 마감을 남은 일수로 바꾼다. 연도가 없으므로 오늘과 가까운 쪽으로 고른다.
  function daysUntil(month, day) {
    if (!(month >= 1 && month <= 12) || !(day >= 1 && day <= 31)) return null;
    let target = Date.UTC(kst.getUTCFullYear(), month - 1, day);
    if (target < todayUtc - 183 * 86400000) target = Date.UTC(kst.getUTCFullYear() + 1, month - 1, day);
    const diff = Math.round((target - todayUtc) / 86400000);
    return Number.isFinite(diff) ? diff : null;
  }

  // 카드 한 장의 글에서 마감까지 남은 일수를 읽는다. D-n, n일 남음, 오늘 마감, n일 지남, 날짜 표기를 모두 본다.
  function readDays(text) {
    let m = text.match(/D\s*-\s*(\d+)/i);
    if (m) return Number(m[1]);
    if (/D\s*-?\s*day/i.test(text)) return 0;
    if ((m = text.match(/(\d+)\s*일\s*남음/))) return Number(m[1]);
    if (/오늘\s*(?:마감|까지)/.test(text)) return 0;
    if ((m = text.match(/(\d+)\s*일\s*지남/))) return -Number(m[1]);
    if ((m = text.match(/D\s*\+\s*(\d+)/i))) return -Number(m[1]);
    // '11.05 ~ 11.11'(신청기간)은 뒤쪽 날짜가 마감, '11.11 까지'·'11.11 마감'은 그 날이 마감이다.
    if ((m = text.match(/~\s*(\d{1,2})\s*[./]\s*(\d{1,2})/))) return daysUntil(Number(m[1]), Number(m[2]));
    if ((m = text.match(/(\d{1,2})\s*[./]\s*(\d{1,2})\s*(?:까지|마감)/))) return daysUntil(Number(m[1]), Number(m[2]));
    return null;
  }

  // 카드 하나를 감싸는 가장 작은 요소를 찾는다: 캠페인 번호가 하나뿐이면서 마감 문구를 담은 상위 요소.
  // 마감 표기가 없는 카드(선정 목록의 일부 등)는 li 단위를 카드로 본다.
  function cardFor(a) {
    let el = a;
    let fallback = null;
    while (el && el !== document.body) {
      const ids = new Set(
        [...el.querySelectorAll('a[href*="/cp/?id="]')]
          .map((x) => ((x.getAttribute("href") || "").match(ID_RE) || [])[1])
          .filter(Boolean)
      );
      if (ids.size <= 1) {
        if (!fallback && (el.tagName === "LI" || el.hasAttribute("data-product"))) fallback = el;
        if (DDAY_RE.test(norm(el.textContent))) return el;
      }
      el = el.parentElement;
    }
    return fallback || a;
  }

  function pickTitle(el) {
    const named = el.querySelector("dt.tit, .tit, dt.tit a");
    let title = named ? norm(named.textContent) : "";
    if (title) return title;
    // 제목 클래스가 없으면: 마감·신청수 문구가 아닌 글을 가진 첫 링크(또는 이미지 alt).
    for (const a of el.querySelectorAll('a[href*="/cp/?id="]')) {
      const t = norm(a.textContent);
      if (t && !DDAY_RE.test(t) && !/신청\s*\d+/.test(t)) return t;
    }
    const img = el.querySelector("img[alt]");
    return img ? norm(img.getAttribute("alt")) : "";
  }

  function pickProvided(el, title) {
    const named = el.querySelector("dd.sub_tit, .sub_tit");
    if (named && norm(named.textContent)) return norm(named.textContent);
    const paras = [...el.querySelectorAll("p, dd")].map((p) => norm(p.textContent)).filter(Boolean);
    return paras.find((t) => t !== title && !DDAY_RE.test(t) && !/신청\s*\d+/.test(t)) || "";
  }

  // 유형: 카드의 '방문형·배송형' 배지. 배지가 없으면 글에서 찾는다.
  const KINDS = ["방문형", "배송형", "기자단", "클립", "구매평", "숙박형", "서비스형"];
  function pickKind(el, text) {
    const badge = norm((el.querySelector("em.type, .type") || {}).textContent);
    const fromBadge = KINDS.find((k) => badge.includes(k));
    if (fromBadge) return fromBadge;
    return KINDS.find((k) => text.includes(k)) || null;
  }

  function readCards() {
    const cards = new Map();
    // 1) 캠페인 상세로 가는 링크가 있는 카드 (공개 목록·마이페이지 모두 이 형태)
    for (const a of document.querySelectorAll('a[href*="/cp/?id="]')) {
      const id = ((a.getAttribute("href") || "").match(ID_RE) || [])[1];
      if (!id || cards.has(id)) continue;
      cards.set(id, cardFor(a));
    }
    // 2) 링크 없이 data-product 로만 표시된 카드(스크립트로 이동하는 화면)도 읽는다.
    for (const li of document.querySelectorAll("li[data-product]")) {
      const id = norm(li.getAttribute("data-product") || "");
      if (/^\d+$/.test(id) && !cards.has(id)) cards.set(id, li);
    }
    const out = [];
    for (const [id, el] of cards) {
      const text = norm(el.textContent);
      const title = pickTitle(el);
      if (!title && !text) continue;
      out.push({
        campaignId: id,
        title,
        provided: pickProvided(el, title),
        kind: pickKind(el, text),
        daysLeft: readDays(text),
        href: `/cp/?id=${id}`,
      });
    }
    return out;
  }

  const bodyText = norm(document.body ? document.body.textContent : "");
  const loginWall = /로그인\s*한\s*회원만\s*접근/.test(bodyText);
  if (loginWall && readCards().length === 0) {
    throw new Error("강남맛집 로그인이 필요합니다. 크롬에서 강남맛집에 로그인해 주세요.");
  }

  // 목록은 스크롤하면 같은 카드가 이어 붙는다(무한 스크롤). 카드 수가 안정될 때까지 내린다.
  let count = -1;
  let same = 0;
  for (let i = 0; i < maxRounds && same < 2; i++) {
    const now2 = readCards().length;
    same = now2 === count ? same + 1 : 0;
    count = now2;
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(sleepMs);
  }
  return readCards();
}
