import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { scrapeSeoulouba } from "../src/seoulouba_parse.js";

async function run(html) {
  const dom = new JSDOM(html, { url: "https://seoulouba.co.kr/mypage/my_campaign.php" });
  Object.assign(globalThis, { document: dom.window.document, window: dom.window });
  dom.window.scrollTo = () => {};
  return scrapeSeoulouba({ sleepMs: 1, maxRounds: 4 });
}

test("서울오빠: 카드에서 번호·제목·제공내역·유형·남은 일수를 읽는다", async () => {
  const cards = await run(readFileSync(new URL("./fixtures/seoulouba.html", import.meta.url), "utf8"));
  assert.equal(cards.length, 2);
  assert.deepEqual(cards[0], {
    campaignId: "1110001",
    title: "[테스트/가상] 예시 카페",
    provided: "예시 음료 2잔 + 디저트 1개 제공",
    kind: "방문형",
    daysLeft: 7,
    href: "https://seoulouba.co.kr/campaign/?c=1110001",
  });
  assert.equal(cards[1].daysLeft, 0, "'D-day'는 남은 일수 0으로 읽는다");
  assert.equal(cards[1].kind, "구매평", "배지 문구에서 유형을 읽는다");
});

test("서울오빠: 카드가 없으면 빈 목록", async () => {
  assert.deepEqual(await run("<html><body><p>없음</p></body></html>"), []);
});

test("서울오빠: 마감 지난 표기도 읽는다", async () => {
  const html = `<ul class="campaign_wbox"><li class="campaign_content">
    <a href="https://seoulouba.co.kr/campaign/?c=1110003"><strong class="s_campaign_title">[테스트/가상] 예시 식당</strong></a>
    <div class="t_basic"><span class="basic_blue">예시 식사권 제공</span></div>
    <div class="campaign_day_people"><div class="d_day"><span>D+2</span></div></div>
  </li></ul>`;
  const cards = await run(html);
  assert.deepEqual(cards.map((c) => c.daysLeft), [-2]);
});
