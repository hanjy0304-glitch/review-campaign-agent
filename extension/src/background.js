// 주기적으로(기본 3시간) 리뷰노트 '진행중 체험단'을 읽어 Notion 표에 저장한다.
// 사이트 로그인은 사용자가 크롬에서 평소처럼 해 둔 상태를 그대로 쓴다. 아이디·비밀번호·쿠키는 읽거나 저장하지 않는다.
import { scrapeReviewnote } from "./reviewnote_parse.js";
import { NotionApi, ORIGIN, parseNotionId, syncCards } from "./notion.js";

const LIST_URL = `${ORIGIN}/users/my_campaign?menuLayout=true&tab=ongoing`;
const ALARM = "collect";
const PERIOD_MIN = 180;

async function setStatus(status) {
  await chrome.storage.local.set({ status: { ...status, at: new Date().toISOString() } });
  await chrome.action?.setBadgeText?.({ text: status.ok ? "" : "!" });
}

function waitForLoad(tabId) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("페이지 로딩 시간 초과"));
    }, 30000);
    function onUpdated(id, info) {
      if (id === tabId && info.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

async function readCards() {
  const tab = await chrome.tabs.create({ url: LIST_URL, active: false });
  try {
    await waitForLoad(tab.id);
    const current = await chrome.tabs.get(tab.id);
    if (!current.url.startsWith(`${ORIGIN}/users/my_campaign`)) {
      throw new Error("리뷰노트 로그인이 필요합니다. 크롬에서 리뷰노트에 로그인해 주세요.");
    }
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: scrapeReviewnote });
    return result;
  } finally {
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}

export async function collect() {
  try {
    const { notionToken, notionDb } = await chrome.storage.local.get(["notionToken", "notionDb"]);
    if (!notionToken || !notionDb) throw new Error("설정 화면에서 Notion 토큰과 표 주소를 입력해 주세요.");
    const cards = await readCards();
    const result = await syncCards(new NotionApi(notionToken, parseNotionId(notionDb)), cards);
    await setStatus({ ok: true, count: cards.length, ...result });
  } catch (e) {
    await setStatus({ ok: false, error: e.message });
  }
}

chrome.runtime.onInstalled.addListener(() => chrome.alarms.create(ALARM, { periodInMinutes: PERIOD_MIN }));
chrome.runtime.onStartup.addListener(collect);
chrome.alarms.onAlarm.addListener((a) => a.name === ALARM && collect());
chrome.runtime.onMessage.addListener((msg) => msg === "collect-now" && collect());
