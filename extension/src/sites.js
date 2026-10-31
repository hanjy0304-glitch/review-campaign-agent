// 지원 사이트 목록. 수집기(background.js)는 이 목록의 사이트를 하나씩 읽는다.
// 새 사이트를 추가하는 절차는 docs/add-site.md 를 참고한다.
// scrape 는 chrome.scripting.executeScript 의 func 로 페이지에 주입되므로,
// 바깥 변수·import 에 의존하지 않는 하나의 함수여야 한다 (reviewnote_parse.js 참고).
import { scrapeReviewnote } from "./reviewnote_parse.js";

export const SITES = [
  {
    key: "reviewnote",
    name: "리뷰노트",
    origin: "https://www.reviewnote.co.kr",
    // 로그인 없이 열리는 첫 화면(메인 등)으로 리다이렉트되면 로그인이 필요한 상태다.
    listUrl: "https://www.reviewnote.co.kr/users/my_campaign?menuLayout=true&tab=ongoing",
    loggedInPrefix: "https://www.reviewnote.co.kr/users/my_campaign",
    loginRequiredMessage: "리뷰노트 로그인이 필요합니다. 크롬에서 리뷰노트에 로그인해 주세요.",
    scrape: scrapeReviewnote,
  },
];
