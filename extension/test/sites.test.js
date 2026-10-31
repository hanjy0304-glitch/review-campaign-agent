import { test } from "node:test";
import assert from "node:assert/strict";
import { SITES } from "../src/sites.js";

test("사이트 목록은 키가 유일하고 수집 함수를 가진다", () => {
  const keys = SITES.map((s) => s.key);
  assert.equal(new Set(keys).size, keys.length);
  for (const s of SITES) {
    assert.equal(typeof s.scrape, "function", `${s.key} scrape`);
    assert.ok(s.listUrl.startsWith(`${s.origin}/`), `${s.key} listUrl`);
    assert.ok(s.listUrl.startsWith(s.loggedInPrefix), `${s.key} 로그인 확인 접두사`);
    assert.ok(s.loginRequiredMessage.includes(s.name));
  }
});

test("reviewnote 가 목록에 있다", () => {
  assert.ok(SITES.some((s) => s.key === "reviewnote" && s.name === "리뷰노트"));
});

test("디너의여왕·리뷰플레이스 가 목록에 있다", () => {
  assert.ok(SITES.some((s) => s.key === "dinnerqueen" && s.name === "디너의여왕"));
  assert.ok(SITES.some((s) => s.key === "reviewplace" && s.name === "리뷰플레이스"));
});
