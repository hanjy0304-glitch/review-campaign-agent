import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapePopomon } from "../src/popomon_parse.js";

const NOW = new Date("2026-11-09T00:00:00Z");

async function run(html, options = {}) {
  const dom = new JSDOM(html, { url: "https://popomon.com/next/mypage" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapePopomon({ sleepMs: 1, maxRounds: 3, now: NOW, ...options });
}

test("포포몬: 카드에서 번호·제목·제공내역·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/popomon.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 4);
  assert.deepEqual(cards[0], {
    campaignId: "336001",
    title: "[식품/테스트] 예시 약과 세트",
    provided: "19일 남음 2.2만원 상당의 예시 약과 세트",
    kind: "배송형",
    daysLeft: 19,
    href: "/next/campaign/336001",
  });
  assert.equal(cards[1].daysLeft, 3, "'D-3'를 3일로 읽는다");
  assert.equal(cards[1].kind, "방문형");
  assert.equal(cards[2].daysLeft, 0, "'오늘 마감'은 0일");
  assert.equal(cards[2].kind, "기자단");
  assert.equal(cards[3].daysLeft, -2, "'2일 지남'은 음수");
  assert.equal(cards[3].kind, "방문형");
});

test("포포몬: 카드가 없으면 빈 목록", async () => {
  assert.deepEqual(await run("<html><body><p>없음</p></body></html>"), []);
});
