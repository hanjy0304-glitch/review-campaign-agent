// 구조 캡처 도우미 (개발용): 로그인된 화면에서 카드 하나의 HTML 구조를 개인정보를 가려 복사한다.
// 사용법: 북마크로 등록 → 화면에서 북마크 클릭 → 카드 안의 글자를 클릭 → 클립보드에 복사됨.
// 이 코드는 페이지 화면(DOM)만 읽는다. 쿠키·저장소·비밀번호는 읽지 않고 어디로도 전송하지 않는다.
(function () {
  // 아래 길이 이하의 짧은 글자(상태·유형 등)와 날짜·D-day 는 남긴다
  var KEEP_MAX = 8;
  var KEEP_RE = /^(D[-+]\d+|\d{1,4}[.\-\/]\d{1,2}([.\-\/]\d{1,2})?)$/;
  var SKIP = { SCRIPT: 1, STYLE: 1, SVG: 1, NOSCRIPT: 1, IFRAME: 1, HEADER: 1, NAV: 1, FOOTER: 1, ASIDE: 1, SELECT: 1 };
  // 위로 올라가다 아래 요소를 포함한 덩어리에서 멈춘다 (메뉴·필터·검색칸이 섞인 영역은 카드가 아님)
  var STOP = "select,nav,header,footer,aside,input,form";

  function maskText(t) {
    t = t.replace(/\s+/g, " ").trim();
    if (!t) return "";
    if (t.length <= KEEP_MAX || KEEP_RE.test(t)) return t;
    return "***(" + t.length + "자)";
  }
  function maskAttr(name, v) {
    if (name === "class" || name === "type" || name === "role") return v;
    return v.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, "***").replace(/\d{5,}/g, "***");
  }
  function dump(el, depth) {
    if (SKIP[el.tagName.toUpperCase()]) return "";
    var pad = new Array(depth + 1).join("  ");
    var attrs = "";
    for (var i = 0; i < el.attributes.length; i++) {
      var a = el.attributes[i];
      if (a.name === "style" || a.name === "srcset" || a.name === "src" || a.name === "value") continue;
      attrs += " " + a.name + '="' + maskAttr(a.name, a.value) + '"';
    }
    var out = pad + "<" + el.tagName.toLowerCase() + attrs + ">\n";
    for (var n = el.firstChild; n; n = n.nextSibling) {
      if (n.nodeType === 3) {
        var t = maskText(n.nodeValue);
        if (t) out += pad + "  " + t + "\n";
      } else if (n.nodeType === 1) {
        out += dump(n, depth + 1);
      }
    }
    return out;
  }
  function pick(target) {
    var el = target;
    while (el.parentElement && el.parentElement !== document.body && !el.parentElement.querySelector(STOP)) {
      el = el.parentElement;
    }
    return el;
  }
  function done(text) {
    var ok = function () { alert("복사되었습니다. 채팅에 붙여넣으세요.\n(" + text.length + "자)"); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok, function () { prompt("복사해서 붙여넣으세요:", text); });
    } else {
      prompt("복사해서 붙여넣으세요:", text);
    }
  }
  alert("카드 안의 글자(제목 등)를 클릭하세요.");
  document.addEventListener("click", function h(e) {
    e.preventDefault();
    e.stopPropagation();
    document.removeEventListener("click", h, true);
    done("URL경로: " + location.pathname + location.search.replace(/\d{5,}/g, "***") + "\n" + dump(pick(e.target), 0));
  }, true);
})();
