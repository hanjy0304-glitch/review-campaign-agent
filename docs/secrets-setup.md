# 값 등록하기 (GitHub Secrets)

**이 단계에서 하는 일:** 앞 단계에서 받은 토큰과 번호를 GitHub 에 등록합니다. 에이전트가 텔레그램과 Notion 에 접속할 때 이 값을 사용합니다.
**끝나면 얻는 것:** 등록된 값 4개
**걸리는 시간:** 값 하나당 1분

Secrets 는 GitHub 이 비밀 값을 저장하는 기능입니다. 한 번 등록하면 화면에 다시 표시되지 않고, 에이전트만 사용할 수 있습니다. 토큰을 파일이나 채팅에 적지 말고 이 방법으로만 등록하세요.

## 등록할 값 4개

| 이름 (Name) | 설명 | 받는 곳 |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 | [텔레그램 1번](telegram-setup.md) |
| `TELEGRAM_CHAT_ID` | 알림을 받을 텔레그램 대화방 번호 | [텔레그램 2번](telegram-setup.md) |
| `NOTION_TOKEN` | Notion 연결 시크릿 키 | [Notion 2번](notion-setup.md) |
| `NOTION_DATABASE_ID` | 체험단 관리 표의 id | [Notion 4번](notion-setup.md) |

값은 한꺼번에 모을 필요 없습니다. **봇 토큰과 Notion 시크릿 키를 먼저 등록**하세요. chat_id 와 표 id 는 그 두 값을 등록한 뒤에 버튼으로 확인할 수 있습니다 (README 5단계).

`USER_CONFIG` 는 필요하지 않습니다. 알림 시점(기본: 글 마감 3일 전·1일 전·당일, 방문 1일 전·당일)을 바꾸고 싶을 때만 등록합니다.

## 등록 방법 (값마다 반복)

1. 내 저장소 페이지에서 위쪽 **Settings** 탭을 누릅니다. Settings 탭이 안 보이면 저장소 주인 계정으로 로그인했는지 확인하세요.
2. 왼쪽 메뉴에서 **Secrets and variables** 를 누르고, 펼쳐진 목록에서 **Actions** 를 누릅니다.
3. **New repository secret** 버튼을 누릅니다.
4. **Name** 칸에 위 표의 이름을 그대로 입력합니다. 대문자와 밑줄(`_`)까지 똑같아야 합니다.
5. **Secret** 칸에 값을 붙여넣습니다. 앞뒤에 공백이나 줄바꿈이 들어가지 않게 주의하세요.
6. **Add secret** 을 누릅니다.

값을 바꾸려면 같은 이름으로 다시 등록하면 덮어쓰기가 됩니다.

## 확인하기
- Secrets 목록에 이름 4개가 보이면 등록은 끝났습니다. 값이 맞는지는 [README 6단계 연결 확인](../README.md#6단계-연결-확인)에서 확인합니다.

## 값이 노출됐다면
노출된 값은 새로 발급하고 다시 등록하세요.
- 텔레그램 봇 토큰: 텔레그램에서 `@BotFather` 에게 `/revoke` 를 보내 새 토큰을 받고 `TELEGRAM_BOT_TOKEN` 을 다시 등록합니다.
- Notion 시크릿 키: Notion 통합 설정 화면에서 시크릿 키를 다시 발급하고 `NOTION_TOKEN` 을 다시 등록합니다.

문제가 생기면 [문제 해결](troubleshooting.md)을 보세요.
