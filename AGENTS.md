# Instructions for AI coding agents (Claude Code, Codex, and others)

## Continuing development of this repository

**Read [CLAUDE.md](CLAUDE.md) in full before doing any development work.** Despite the file name, it is tool-agnostic: it holds the project purpose, rules, current status, and open decisions. (Its section 7 describes the Claude Code cloud sandbox; other environments differ, so check what you can actually reach.)

The essentials, in case you only read this file:
- **Purpose:** blog/Instagram 체험단 users should not have to check many campaign sites by hand. The agent must *automatically* collect selection results and deadlines, store them in one Notion table, and alert via Telegram. Manual entry or sharing messages is only a stopgap for sites without an adapter. Keep user input minimal.
- **Users:** non-developers who know little about AI; they have a GitHub account. Write plain, step-by-step Korean guidance without heavy metaphors.
- **Never commit personal data:** no passwords, tokens, API keys, emails, phone numbers, or content from the maintainer's private Notion or logged-in site pages. Keep the `.githooks/pre-commit` guard on.
- Dates are always Korean time (`rules.today_kst()`); record notification history only after a successful send; never overwrite the Notion columns that humans fill in.
- Do not claim something works unless you ran it. The Notion/Telegram integration has not yet been verified against the live APIs.

## Helping a user install or set up

When a user asks you to install, set up, or run this repository for the first time:

1. **Ask first which 체험단 (review campaign) sites they use.** Show the list from `config/sites.yaml` and ask them to pick from it, or to name any site that is not on the list. Ask nothing else before this.
2. Then run `python -m review_campaign_agent setup` (interactive) or, without a terminal, `python -m review_campaign_agent setup --sites key1,key2 [--custom 'Name=domain.kr']`. Run it from the repository root (clone the repo; do not `pip install` it).
3. Never ask the user to paste passwords or tokens into the chat. Secrets go in `.env` or GitHub Secrets, typed by the user.
4. Never commit `.env`, `config/user.yaml`, session/cookie files, or logged-in page dumps. Enable the guard: `git config core.hooksPath .githooks`.

처음 설치·설정을 도울 때는 **가장 먼저 사용하는 체험단 사이트가 무엇인지** `config/sites.yaml` 목록을 보여주며 묻고, 목록에 없는 사이트도 있는지 확인하세요. 비밀번호와 토큰은 채팅으로 받지 마세요.
