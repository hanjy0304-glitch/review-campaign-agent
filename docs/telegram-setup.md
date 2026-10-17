# 텔레그램 알림 연결

## 1. 봇 만들기
텔레그램에서 `@BotFather` 를 검색해 대화를 시작하고 `/newbot` 을 보냅니다. 안내에 따라 이름을 정하면 **봇 토큰**을 알려줍니다. 이 값을 `TELEGRAM_BOT_TOKEN` 으로 `.env` 또는 GitHub Secrets 에 넣습니다. 토큰을 아는 사람은 누구나 이 봇으로 메시지를 보낼 수 있으니 공개하지 마세요.

## 2. 내 chat_id 찾기
1. 만든 봇을 검색해 들어가서 아무 메시지(예: `안녕`)를 보냅니다.
2. 실행: `python -m review_campaign_agent telegram-chat-id`
3. 출력된 숫자를 `TELEGRAM_CHAT_ID` 로 저장합니다.

## 3. 연결 확인
```
python -m review_campaign_agent telegram-test
```
텔레그램에 테스트 메시지가 오면 끝입니다.

## 4. 알림 미리보기
```
python -m review_campaign_agent run --dry-run --summary
```
Notion 표를 읽어서 오늘 보낼 알림을 보내지 않고 화면에만 보여줍니다.
