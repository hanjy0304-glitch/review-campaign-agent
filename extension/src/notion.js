// Notion 표(체험단 관리) 저장. 칸 이름은 review_campaign_agent/notion_schema.py 와 같아야 한다.
// 사이트에서 읽은 값 중 에이전트 칸(선정상태·선정일·글마감일·링크·입력방식·고유키)만 쓰고,
// 사람 칸(진행단계·방문일·페이백·메모 등)은 건드리지 않는다. 제공내역·유형은 새 행을 만들 때만 채운다.
const API = "https://api.notion.com/v1";
const NOTION_VERSION = "2022-06-28";

export const SITE_KEY = "reviewnote";
export const SITE_NAME = "리뷰노트";
export const ORIGIN = "https://www.reviewnote.co.kr";

export function parseNotionId(urlOrId) {
  // "제목-<32자리>" 형태이므로 제목 끝 글자(a-f)가 id 에 섞이지 않도록 하이픈을 지우기 전에 경계를 본다
  const path = String(urlOrId).split("?")[0].split("#")[0];
  const plain = path.match(/(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])/g);
  const dashed = path.match(/(?<![0-9a-fA-F])[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?![0-9a-fA-F])/g);
  const found = plain?.at(-1) ?? dashed?.at(-1)?.replace(/-/g, "");
  if (!found) throw new Error("Notion 표 주소에서 id 를 찾지 못했습니다.");
  const h = found.toLowerCase();
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// 한국시간 기준 오늘 (YYYY-MM-DD). Date 는 UTC 로 다룬다.
export function todayKst(now = new Date()) {
  return new Date(now.getTime() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

export function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

const text = (kind, v) => ({ [kind]: v ? [{ type: "text", text: { content: String(v).slice(0, 1900) } }] : [] });
const select = (v) => ({ select: v ? { name: v } : null });
const date = (v) => ({ date: v ? { start: v } : null });

export function toRow(card, today) {
  return {
    key: `${SITE_KEY}:${card.campaignId}`,
    title: card.title || `리뷰노트 #${card.campaignId}`,
    deadline: card.daysLeft == null ? null : addDays(today, card.daysLeft),
    url: ORIGIN + card.href,
    kind: card.kind,
    provided: card.provided,
  };
}

function newPageProperties(row, today) {
  const props = {
    체험단명: text("title", row.title),
    사이트: select(SITE_NAME),
    선정상태: select("선정"),
    선정일: date(today),
    글마감일: date(row.deadline),
    링크: { url: row.url },
    입력방식: select("자동"),
    고유키: text("rich_text", row.key),
  };
  if (row.kind) props["유형"] = select(row.kind);
  if (row.provided) props["제공내역"] = text("rich_text", row.provided);
  return props;
}

export class NotionApi {
  constructor(token, databaseId, fetchFn = fetch) {
    this.token = token;
    this.db = databaseId;
    this.fetch = fetchFn;
  }

  async request(method, path, body) {
    let res;
    try {
      res = await this.fetch(API + path, {
        method,
        headers: {
          Authorization: `Bearer ${this.token}`,
          "Notion-Version": NOTION_VERSION,
          "Content-Type": "application/json",
        },
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch {
      throw new Error("Notion 연결 실패"); // 오류 메시지에 토큰이 섞이지 않게 원인은 남기지 않는다
    }
    if (!res.ok) {
      let message = "";
      try {
        message = (await res.json()).message || "";
      } catch {}
      throw new Error(`Notion API 오류 ${res.status}: ${message}`);
    }
    return res.json();
  }

  async findByKey(key) {
    const data = await this.request("POST", `/databases/${this.db}/query`, {
      page_size: 1,
      filter: { property: "고유키", rich_text: { equals: key } },
    });
    return data.results[0] || null;
  }
}

// 읽은 카드들을 표에 반영한다. 반환: { added, updated, unchanged }
export async function syncCards(api, cards, now = new Date()) {
  const today = todayKst(now);
  const result = { added: 0, updated: 0, unchanged: 0 };
  for (const card of cards) {
    const row = toRow(card, today);
    const page = await api.findByKey(row.key);
    if (!page) {
      await api.request("POST", "/pages", {
        parent: { database_id: api.db },
        properties: newPageProperties(row, today),
      });
      result.added++;
      continue;
    }
    const changes = {};
    const props = page.properties || {};
    if (row.deadline && (props["글마감일"]?.date?.start || null) !== row.deadline) changes["글마감일"] = date(row.deadline);
    if ((props["선정상태"]?.select?.name || null) !== "선정") changes["선정상태"] = select("선정");
    if (Object.keys(changes).length) {
      await api.request("PATCH", `/pages/${page.id}`, { properties: changes });
      result.updated++;
    } else {
      result.unchanged++;
    }
  }
  return result;
}
