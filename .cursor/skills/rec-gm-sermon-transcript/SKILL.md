---
name: rec-gm-sermon-transcript
description: Pull REC GM KU1/KU2 sermon and tanya jawab, cut sections, export Markdown, and return readable file links. Use when the user asks for REC GM sermon transcripts, khotbah MD, or tanya jawab export.
---

# REC GM sermon + Q&A → Markdown

## Scope
- **REC GM only** unless the user names another campus.
- Default targets: latest **KU1** and **KU2** for the service date the user means ("today" = Asia/Jakarta).
- Parts: **sermon** and **tanya jawab** only.

## Do
1. Find the matching REC GM KU1 and KU2 YouTube videos.
2. Download the videos when possible.
3. Cut sermon and tanya-jawab segments.
4. Export one `.md` file per part (4 files typical: ku1-sermon, ku1-tanya-jawab, ku2-sermon, ku2-tanya-jawab).
5. Put the `.md` files where the user can open them (repo/workspace path) and **link those files in the reply**. Do not wait to be asked for links.

## Do not
- Do **not** upload to Google Drive, Docs, Dropbox, email, or any other service unless the user explicitly asks.
- Do not offer extras the user did not ask for.
- Do not ask follow-up preference questions when the request is clear.
- Do not pad the reply with options, alternatives, or "want me to also…".
- Do not process Nginden/KU3/other campuses unless asked.

## Reply shape
- Short status (what was done / blocked).
- List each MD with its openable link (repo blob/raw or workspace path only).
- Stop.
