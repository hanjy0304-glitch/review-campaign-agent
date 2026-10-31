import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapeReviewplace } from "../src/reviewplace_parse.js";

async function run(html) {
  const dom = new JSDOM(html, { url: "https://www.reviewplace.co.kr/my/" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapeReviewplace({ sleepMs: 1, maxRounds: 4 });
}

test("리뷰플레이스: 카드에서 번호·제목·제공내역·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/reviewplace.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 2);
  assert.deepEqual(cards[0], {
    campaignId: "317001",
    title: "[테스트/가상] 예시 만두 정말 짱이당!",
    provided: "예시 만두 4종세트(고기, 김치, 갈비, 매운)",
    kind: null,
    daysLeft: 3,
    href: "/pr/?id=317001&rp_apply_refresh=20260814_pc_apply_return2",
  });
  assert.equal(cards[1].daysLeft, 0, "'오늘마감'은 남은 일수 0으로 읽는다");
  assert.equal(cards[1].kind, "기자단");
});

test("리뷰플레이스: 신청수 문단을 제공내역로 읽지 않는다", async () => {
  const html = `<div class="item"><a href="/pr/?id=317003">
    <div class="txt_wrap"><p class="tit">제목 하나</p></div>
    <div class="date_wrap"><p class="date"><em class="d_ico">D</em> - 1</p>
    <div class="num"><p>신청 12<span> / 5명</span></p></div></div></a></div>`;
  const cards = await run(html);
  assert.equal(cards.length, 1);
  assert.equal(cards[0].provided, "");
  assert.equal(cards[0].daysLeft, 1);
});
