# 텔레그램 연결

**이 단계에서 하는 일:** 알림을 보낼 텔레그램 봇을 만들고, 그 알림을 받을 내 대화방 번호를 확인합니다.
**끝나면 얻는 것:** 봇 토큰, chat_id (대화방 번호). 두 값은 [값 등록](secrets-setup.md)에서 등록합니다.
**걸리는 시간:** 약 5분
**필요한 것:** 텔레그램 앱 (폰 또는 PC)

## 1. 봇 만들기 (README 2단계에서 진행)
1. 텔레그램 검색창에 `BotFather` 를 입력하고, 이름 옆에 파란 체크 표시가 있는 **@BotFather** 를 엽니다.
2. `/newbot` 을 보냅니다.
3. 봇 이름을 입력합니다 (예: `내 체험단 알림`).
4. 봇 아이디를 입력합니다. 영문으로 작성하고 **끝이 `bot` 으로 끝나야** 합니다 (예: `my_review_alert_bot`).
5. 완료 메시지에 `123456789:AAH...` 같은 긴 문자열이 나옵니다. 이것이 **봇 토큰**입니다. 복사해 두세요.
6. [값 등록](secrets-setup.md)에서 이 값을 `TELEGRAM_BOT_TOKEN` 이라는 이름으로 등록합니다. 토큰은 다른 사람에게 보이지 마세요.

## 2. chat_id 확인하기 (README 5단계에서 진행)
에이전트가 알림을 보낼 대화방 번호입니다.

1. 텔레그램에서 방금 만든 봇을 검색해 열고 **시작(Start)** 을 누른 뒤, 아무 메시지(예: `안녕`)를 보냅니다. 이 메시지가 없으면 번호를 찾을 수 없습니다.
2. `TELEGRAM_BOT_TOKEN` 이 [등록](secrets-setup.md)되어 있어야 합니다. 아직 안 했다면 먼저 등록하세요.
3. GitHub 내 저장소의 **Actions** 탭 → 왼쪽 **연결 확인** → **Run workflow** 를 누릅니다.
4. 동작을 `telegram-chat-id` 로 선택하고 **Run workflow** 를 누릅니다.
5. 1분쯤 기다리면 목록에 실행이 나타나고 초록색 체크가 표시됩니다. 그 실행을 눌러 **connections** → **Run** 을 열면 맨 아래에 숫자가 있습니다. 이것이 chat_id 입니다.
6. 이 값을 `TELEGRAM_CHAT_ID` 라는 이름으로 등록합니다.

## 3. 연결 확인
[README 6단계](../README.md#6단계-연결-확인)에서 `telegram-test` 를 실행해 텔레그램으로 테스트 메시지가 오는지 확인합니다.

## 개발자용: 내 컴퓨터에서 실행하기
`.env` 파일에 `TELEGRAM_BOT_TOKEN` 을 넣고 실행합니다.

```
python -m review_campaign_agent telegram-chat-id
python -m review_campaign_agent telegram-test
```

안 될 때는 [문제 해결](troubleshooting.md)을 보세요.
