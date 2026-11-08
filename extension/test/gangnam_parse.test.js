import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapeGangnam } from "../src/gangnam_parse.js";

// 2026-11-06(금) 09:00 KST 기준. '11.11 까지'까지 5일이 남는다.
const NOW = new Date("2026-11-06T00:00:00Z");

async function run(html, options = {}) {
  const dom = new JSDOM(html, { url: "https://xn--939au0g4vj8sq.net/theme/go/mypage/" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapeGangnam({ sleepMs: 1, maxRounds: 3, now: NOW, ...options });
}

test("강남맛집: 카드에서 번호·제목·제공내역·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/gangnam.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 5);
  assert.deepEqual(cards[0], {
    campaignId: "1110001",
    title: "[테스트/가상] 예시 식당",
    provided: "예시 식사권 2인 (5만원 상당)",
    kind: "방문형",
    daysLeft: 7,
    href: "/cp/?id=1110001",
  });
  assert.equal(cards[1].daysLeft, 2, "'D-2'를 2일로 읽는다");
  assert.equal(cards[1].kind, "기자단");
  assert.equal(cards[2].daysLeft, 0, "'오늘 마감'은 0일");
  assert.equal(cards[3].daysLeft, -3, "'3일 지남'은 음수");
  assert.equal(cards[4].daysLeft, 5, "'11.11 까지'는 오늘(11/6)부터 5일");
});

test("강남맛집: 마감 표기가 날짜 범위면 뒤 날짜를 마감으로 본다", async () => {
  const html = `<ul><li data-product="2220001" class="list_item">
    <a href="/cp/?id=2220001"><img alt="[테스트/가상] 예시 국밥"></a>
    <em class="type">방문형</em><span class="day_c">11.05 ~ 11.20</span>
  </li></ul>`;
  const cards = await run(html);
  assert.equal(cards.length, 1);
  assert.equal(cards[0].daysLeft, 14);
});

test("강남맛집: 제목 클래스가 없으면 링크 글자·이미지 alt에서 제목을 읽는다", async () => {
  const html = `<ul><li class="list_item" data-product="2220002">
    <a href="/cp/?id=2220002"><img alt="[테스트/가상] 예시 파스타"></a>
    <span class="dday"><em class="day_c">4일 남음</em></span>
    <a href="/cp/?id=2220002">[테스트/가상] 예시 파스타 지점</a>
  </li></ul>`;
  const cards = await run(html);
  assert.equal(cards.length, 1);
  assert.equal(cards[0].title, "[테스트/가상] 예시 파스타 지점");
  assert.equal(cards[0].daysLeft, 4);
});

test("강남맛집: 카드가 없으면 빈 목록", async () => {
  assert.deepEqual(await run("<html><body><p>없음</p></body></html>"), []);
});

test("강남맛집: 로그인이 풀린 화면은 실패로 알린다", async () => {
  const html = `<html><body>
    <noscript><div id="validation_check"><h1>다음 항목에 오류가 있습니다.</h1>
    <p>로그인 한 회원만 접근하실 수 있습니다.</p></div></noscript>
  </body></html>`;
  await assert.rejects(() => run(html), /강남맛집 로그인이 필요합니다/);
});
