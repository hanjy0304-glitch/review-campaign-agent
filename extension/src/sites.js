// 지원 사이트 목록. 수집기(background.js)는 이 목록의 사이트를 하나씩 읽는다.
// 새 사이트를 추가하는 절차는 docs/add-site.md 를 참고한다.
// scrape 는 chrome.scripting.executeScript 의 func 로 페이지에 주입되므로,
// 바깥 변수·import 에 의존하지 않는 하나의 함수여야 한다 (reviewnote_parse.js 참고).
import { scrapeReviewnote } from "./reviewnote_parse.js";
import { scrapeDinnerqueen } from "./dinnerqueen_parse.js";
import { scrapeReviewplace } from "./reviewplace_parse.js";
import { scrapeSeoulouba } from "./seoulouba_parse.js";
import { scrapeGangnam } from "./gangnam_parse.js";

export const SITES = [
  {
    key: "gangnam",
    name: "강남맛집",
    // 강남맛집.net(punycode). gangnam-review.net 은 이 주소로 301 리다이렉트되므로 리다이렉트 뒤 주소를 쓴다.
    origin: "https://xn--939au0g4vj8sq.net",
    // 마이페이지('나의 캠페인'). 로그인 없이 열면 alert 뒤 로그인 화면(/bbs/login.php)으로 넘어간다.
    listUrl: "https://xn--939au0g4vj8sq.net/theme/go/mypage/",
    loggedInPrefix: "https://xn--939au0g4vj8sq.net/theme/go/mypage/",
    loginRequiredMessage: "강남맛집 로그인이 필요합니다. 크롬에서 강남맛집에 로그인해 주세요.",
    scrape: scrapeGangnam,
  },
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
  {
    key: "dinnerqueen",
    name: "디너의여왕",
    origin: "https://dinnerqueen.net",
    // 마이페이지('나의캠페인' 위젯). 로그인 없이 열면 메인(/)으로 리다이렉트된다.
    listUrl: "https://dinnerqueen.net/mypage/widget",
    loggedInPrefix: "https://dinnerqueen.net/mypage",
    loginRequiredMessage: "디너의여왕 로그인이 필요합니다. 크롬에서 디너의여왕에 로그인해 주세요.",
    scrape: scrapeDinnerqueen,
  },
  {
    key: "seoulouba",
    name: "서울오빠",
    origin: "https://seoulouba.co.kr",
    // 마이페이지('내 캠페인'). 로그인 없이 열면 로그인 화면(/bbs/login.php)으로 넘어간다.
    listUrl: "https://seoulouba.co.kr/mypage/my_campaign.php",
    loggedInPrefix: "https://seoulouba.co.kr/mypage/my_campaign.php",
    loginRequiredMessage: "서울오빠 로그인이 필요합니다. 크롬에서 서울오빠에 로그인해 주세요.",
    scrape: scrapeSeoulouba,
  },
  {
    key: "reviewplace",
    name: "리뷰플레이스",
    origin: "https://www.reviewplace.co.kr",
    // 마이페이지('내 캠페인' 탭). 로그인 없이 열면 로그인 화면(/bbs/login.php)으로 넘어간다.
    listUrl: "https://www.reviewplace.co.kr/my/",
    loggedInPrefix: "https://www.reviewplace.co.kr/my/",
    loginRequiredMessage: "리뷰플레이스 로그인이 필요합니다. 크롬에서 리뷰플레이스에 로그인해 주세요.",
    scrape: scrapeReviewplace,
  },
];
