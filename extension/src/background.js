// 주기적으로(기본 3시간) 지원 사이트(src/sites.js)의 '진행중 체험단'을 읽어 Notion 표에 저장한다.
// 사이트 로그인은 사용자가 크롬에서 평소처럼 해 둔 상태를 그대로 쓴다. 아이디·비밀번호·쿠키는 읽거나 저장하지 않는다.
import { SITES } from "./sites.js";
import { NotionApi, parseNotionId, syncCards } from "./notion.js";

const ALARM = "collect";
const PERIOD_MIN = 30;

let lastCollectAt = 0;
const THROTTLE_MS = 10 * 60 * 1000;

async function throttledCollect() {
  const now = Date.now();
  if (now - lastCollectAt < THROTTLE_MS) return;
  lastCollectAt = now;
  await collect();
}

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

async function readCards(site) {
  const tab = await chrome.tabs.create({ url: site.listUrl, active: false });
  try {
    await waitForLoad(tab.id);
    const current = await chrome.tabs.get(tab.id);
    if (!current.url.startsWith(site.loggedInPrefix)) {
      throw new Error(site.loginRequiredMessage);
    }
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: site.scrape });
    return result;
  } finally {
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}

// 사이트별로 성공·실패를 따로 기록한다. 한 사이트가 막혀도 다른 사이트 수집은 계속한다.
async function collectSite(api, site) {
  try {
    const cards = await readCards(site);
    const result = await syncCards(api, cards, site);
    return { ok: true, count: cards.length, ...result };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

export async function collect() {
  try {
    const { notionToken, notionDb } = await chrome.storage.local.get(["notionToken", "notionDb"]);
    if (!notionToken || !notionDb) throw new Error("설정 화면에서 Notion 토큰과 표 주소를 입력해 주세요.");
    const api = new NotionApi(notionToken, parseNotionId(notionDb));
    const totals = { added: 0, updated: 0, unchanged: 0 };
    const sites = {};
    let ok = true;
    for (const site of SITES) {
      const r = await collectSite(api, site);
      sites[site.name] = r;
      if (r.ok) {
        totals.added += r.added;
        totals.updated += r.updated;
        totals.unchanged += r.unchanged;
      } else {
        ok = false;
      }
    }
    await setStatus({ ok, ...totals, sites });
  } catch (e) {
    await setStatus({ ok: false, error: e.message });
  }
}

chrome.runtime.onInstalled.addListener(() => chrome.alarms.create(ALARM, { periodInMinutes: PERIOD_MIN }));
chrome.runtime.onStartup.addListener(throttledCollect);
chrome.windows?.onCreated?.addListener(throttledCollect);
chrome.alarms.onAlarm.addListener((a) => a.name === ALARM && throttledCollect());
chrome.runtime.onMessage.addListener((msg) => msg === "collect-now" && collect());
