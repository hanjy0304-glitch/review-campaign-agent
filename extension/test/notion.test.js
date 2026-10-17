import { test } from "node:test";
import assert from "node:assert/strict";
import { NotionApi, addDays, parseNotionId, syncCards, todayKst } from "../src/notion.js";

const CARD = {
  campaignId: "1000001",
  title: "[테스트/가상] 예시 커피집",
  provided: "예시 식사권 제공",
  kind: "방문형",
  daysLeft: 17,
  href: "/campaigns/1000001",
};
const NOW = new Date("2026-10-16T16:30:00Z"); // 한국시간 2026-10-17 01:30

function fakeFetch(existing) {
  const calls = [];
  const fn = async (url, init) => {
    const body = init.body ? JSON.parse(init.body) : null;
    calls.push({ method: init.method, path: url.replace("https://api.notion.com/v1", ""), body });
    if (url.endsWith("/query")) return { ok: true, json: async () => ({ results: existing ? [existing] : [] }) };
    return { ok: true, json: async () => ({}) };
  };
  return { fn, calls };
}

test("날짜 계산은 한국시간 기준", () => {
  assert.equal(todayKst(NOW), "2026-10-17");
  assert.equal(addDays("2026-10-17", 17), "2026-11-03");
  assert.equal(addDays("2026-12-30", 3), "2027-01-02");
});

test("Notion 주소에서 id 추출", () => {
  assert.equal(
    parseNotionId("https://www.notion.so/ws/My-Table-0123456789abcdef0123456789abcdef?v=fedcba9876543210fedcba9876543210"),
    "01234567-89ab-cdef-0123-456789abcdef",
  );
  assert.throws(() => parseNotionId("https://example.com"));
});

test("새 캠페인은 에이전트 칸과 제공내역·유형으로 새 행을 만든다", async () => {
  const { fn, calls } = fakeFetch(null);
  const result = await syncCards(new NotionApi("tok", "db1", fn), [CARD], NOW);
  assert.deepEqual(result, { added: 1, updated: 0, unchanged: 0 });
  const created = calls.find((c) => c.method === "POST" && c.path === "/pages").body.properties;
  assert.equal(created["고유키"].rich_text[0].text.content, "reviewnote:1000001");
  assert.equal(created["글마감일"].date.start, "2026-11-03");
  assert.equal(created["선정일"].date.start, "2026-10-17");
  assert.equal(created["선정상태"].select.name, "선정");
  assert.equal(created["입력방식"].select.name, "자동");
  assert.equal(created["링크"].url, "https://www.reviewnote.co.kr/campaigns/1000001");
  assert.equal(created["유형"].select.name, "방문형");
  for (const humanOnly of ["진행단계", "방문일", "페이백", "메모", "방문가능시간"]) {
    assert.equal(humanOnly in created, false, `${humanOnly} 는 쓰면 안 됨`);
  }
});

test("기존 행은 마감일이 달라졌을 때만 마감일만 고친다", async () => {
  const page = { id: "p1", properties: { 글마감일: { date: { start: "2026-11-01" } }, 선정상태: { select: { name: "선정" } } } };
  const { fn, calls } = fakeFetch(page);
  const result = await syncCards(new NotionApi("tok", "db1", fn), [CARD], NOW);
  assert.deepEqual(result, { added: 0, updated: 1, unchanged: 0 });
  const patch = calls.find((c) => c.method === "PATCH");
  assert.deepEqual(Object.keys(patch.body.properties), ["글마감일"]);
});

test("바뀐 것이 없으면 아무것도 쓰지 않는다", async () => {
  const page = { id: "p1", properties: { 글마감일: { date: { start: "2026-11-03" } }, 선정상태: { select: { name: "선정" } } } };
  const { fn, calls } = fakeFetch(page);
  const result = await syncCards(new NotionApi("tok", "db1", fn), [CARD], NOW);
  assert.deepEqual(result, { added: 0, updated: 0, unchanged: 1 });
  assert.equal(calls.some((c) => c.method !== "POST" || c.path !== "/databases/db1/query"), false);
});

test("오류 메시지에 토큰이 들어가지 않는다", async () => {
  const api = new NotionApi("secret_TOKEN", "db1", async () => {
    throw new Error("secret_TOKEN failed");
  });
  await assert.rejects(api.findByKey("k"), (e) => !e.message.includes("secret_TOKEN"));
});
