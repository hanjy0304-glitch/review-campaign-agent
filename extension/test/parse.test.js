import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapeReviewnote } from "../src/reviewnote_parse.js";

async function run(html) {
  const dom = new JSDOM(html, { url: "https://www.reviewnote.co.kr/users/my_campaign" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapeReviewnote({ sleepMs: 1, maxRounds: 4 });
}

test("진행중 카드에서 번호·제목·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/ongoing.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 2);
  assert.deepEqual(cards[0], {
    campaignId: "1000001",
    title: "[테스트/가상] 예시 커피집",
    provided: "예시 식사권 15,000원 제공",
    kind: "방문형",
    daysLeft: 17,
    href: "/campaigns/1000001",
  });
  assert.equal(cards[1].daysLeft, 3);
  assert.equal(cards[1].kind, "배송형");
});

test("카드가 없으면 빈 목록", async () => {
  assert.deepEqual(await run("<html><body><p>없음</p></body></html>"), []);
});

test("D-day 와 마감 지난 표기를 읽는다", async () => {
  const html = `<div><span>#2000001</span><a href="/campaigns/2000001"><b>D-day</b></a><a href="/campaigns/2000001">제목 하나</a></div>
                <div><span>#2000002</span><a href="/campaigns/2000002"><b>D+2</b></a><a href="/campaigns/2000002">제목 둘</a></div>`;
  const cards = await run(html);
  assert.deepEqual(cards.map((c) => c.daysLeft), [0, -2]);
});

test("선정 전 '신청' 상태인 카드는 제외한다", async () => {
  const html = `<div><span>#3000001</span><button>취소</button><span>3 일 남음</span><span>신청 1254 / 5</span><a href="/campaigns/3000001">신청한 체험단</a></div>
                <div><span>#3000002</span><button>취소</button><span>오늘 선정 마감</span><a href="/campaigns/3000002">오늘 마감 체험단</a></div>
                <div><span>#3000003</span><a href="/campaigns/3000003"><b>D-5</b> 리뷰 등록</a><a href="/campaigns/3000003">선정된 체험단</a></div>`;
  const cards = await run(html);
  assert.equal(cards.length, 1);
  assert.equal(cards[0].campaignId, "3000003");
  assert.equal(cards[0].title, "선정된 체험단");
  assert.equal(cards[0].daysLeft, 5);
});

