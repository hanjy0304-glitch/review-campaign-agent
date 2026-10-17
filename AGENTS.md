# Instructions for AI coding agents

When a user asks you to install, set up, or run this repository for the first time:

1. **Ask first which 체험단 (review campaign) sites they use.** Show the list from `config/sites.yaml` and ask them to pick from it, or to name any site that is not on the list. Ask nothing else before this.
2. Then run `python -m review_campaign_agent setup` (interactive) or, without a terminal, `python -m review_campaign_agent setup --sites key1,key2 [--custom 'Name=domain.kr']`. Run it from the repository root (clone the repo; do not `pip install` it).
3. Never ask the user to paste passwords or tokens into the chat. Secrets go in `.env` or GitHub Secrets, typed by the user.
4. Never commit `.env`, `config/user.yaml`, session/cookie files, or logged-in page dumps. Enable the guard: `git config core.hooksPath .githooks`.

처음 설치·설정을 도울 때는 **가장 먼저 사용하는 체험단 사이트가 무엇인지** `config/sites.yaml` 목록을 보여주며 묻고, 목록에 없는 사이트도 있는지 확인하세요. 비밀번호와 토큰은 채팅으로 받지 마세요.
