import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapeDinnerqueen } from "../src/dinnerqueen_parse.js";

async function run(html) {
  const dom = new JSDOM(html, { url: "https://dinnerqueen.net/mypage/widget" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapeDinnerqueen({ sleepMs: 1, maxRounds: 4 });
}

test("디너의여왕: 카드에서 번호·제목·제공내역·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/dinnerqueen.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 2);
  assert.deepEqual(cards[0], {
    campaignId: "1110001",
    title: "[테스트/가상] 예시 카페",
    provided: "예시 음료 2잔 + 디저트 1개 제공",
    kind: "릴스",
    daysLeft: 7,
    href: "/taste/1110001",
  });
  assert.equal(cards[1].daysLeft, 0, "'오늘까지'는 남은 일수 0으로 읽는다");
  assert.equal(cards[1].kind, "배송");
});

test("디너의여왕: 카드가 없으면 빈 목록", async () => {
  assert.deepEqual(await run("<html><body><p>없음</p></body></html>"), []);
});
