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

test("디너의여왕·리뷰플레이스·서울오빠 가 목록에 있다", () => {
  assert.ok(SITES.some((s) => s.key === "dinnerqueen" && s.name === "디너의여왕"));
  const rp = SITES.find((s) => s.key === "reviewplace");
  assert.ok(rp && rp.name === "리뷰플레이스");
  assert.equal(rp.listUrl, "https://www.reviewplace.co.kr/my/cmp_select.php");
  assert.ok(SITES.some((s) => s.key === "seoulouba" && s.name === "서울오빠"));
});

test("강남맛집이 목록에 있고 마이페이지를 연다", () => {
  const gangnam = SITES.find((s) => s.key === "gangnam");
  assert.ok(gangnam && gangnam.name === "강남맛집");
  // gangnam-review.net 은 301 리다이렉트되므로 리다이렉트 뒤 주소(punycode)를 쓴다
  assert.equal(gangnam.origin, "https://xn--939au0g4vj8sq.net");
  assert.equal(gangnam.listUrl, "https://xn--939au0g4vj8sq.net/theme/go/mypage/");
});

test("포포몬이 목록에 있고 마이페이지를 연다", () => {
  const popomon = SITES.find((s) => s.key === "popomon");
  assert.ok(popomon && popomon.name === "포포몬");
  assert.equal(popomon.origin, "https://popomon.com");
  assert.equal(popomon.listUrl, "https://popomon.com/next/mypage");
  assert.equal(popomon.loggedInPrefix, "https://popomon.com/next/mypage");
});

