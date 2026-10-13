---
name: user-collab-style
description: Use on every task for this user to match their preferred working style — results-only replies, autonomous execution without mid-task questions, confirming before irreversible deletions, and rewriting/optimising their prompts. Also use when they give a vague or terse request and you need to infer intent from their habits.
whenToUse: Any task for this user. Especially when they ask to "优化提示词", give a short or ambiguous instruction, or when a task involves deleting/destroying data.
metadata:
  version: 1.0
  author: agent
---

# How to work with this user

## Reply format — results only

They have said explicitly: **don't narrate the process, don't paste logs, don't
explain原理, don't give unsolicited advice.**

- Lead with the outcome: a table or checklist of `item → success/fail/skip`.
- One short line of reason for failures. Nothing more.
- Prefer tables over paragraphs. Chinese, since they write Chinese.
- Do explain *why* something broke — briefly, once, after fixing it. They do
  want root cause, just not a wall of text.

## Execution style — don't stop to ask

They say 「一次跑完，中途不要停下询问，失败项记录下来最后统一汇报」.

- Make reasonable judgement calls and keep going.
- Collect failures and report them together at the end.
- **Exception:** confirm before large irreversible deletions. When they said
  "删掉…以及相关文件" about a 58 GB install, deleting the cheap-to-restore
  items first and asking about the bulk was the right call and they accepted it.
- Never silently install multi-gigabyte software. Ask, or offer as an option.

## Inferring intent from vague requests

They often give short instructions. Before acting:

1. **Read the existing project first.** Their intent is usually a continuation
   of what's on disk, not a new direction. (They asked for "game-making
   software" when the real need was the toolchain for their existing
   Three.js project — installing Unity/Unreal would have been wrong.)
2. **Check `MEMORY.md`** at the workspace root for durable profile facts.
3. If genuinely ambiguous, act on the most probable reading and state the
   assumption in one line.

## Optimising their prompts

When asked to improve a prompt, return:

- A **rewritten prompt** that is specific, constrained, and states the
  acceptance criteria.
- A short **why** for each significant change.
- Keep their intent intact — sharpen, don't redirect.

Typical fixes their prompts need:

| Problem | Fix |
|---|---|
| Vague goal ("帮我弄一下") | Name the deliverable and its acceptance test |
| Missing constraints | Add hard limits (size, VRAM, no-payment, compliance) |
| Mixed asks in one sentence | Split into numbered steps with owners |
| No definition of done | Add "完成标准" — what must be true to call it done |

## Environment gotchas to remember

- **8 GB VRAM** ceiling on every GPU task.
- **GitHub / raw.githubusercontent.com / huggingface.co are blocked**; use
  npmmirror, tuna, ModelScope, hf-mirror.
- **Parallel downloads stall** — sequential `curl -C -` works.
- **PowerShell 5.1** — no `??`, no `?:`. Non-ASCII `.ps1` needs UTF-8 BOM;
  `.bat` must be ASCII-only.
- **Never** put a GitHub download inside `INPUT_TYPES()`/startup code — no
  timeout, deadlocks the main thread.
- Their wired adapter is `以太网`, wireless is `WLAN`.
- When writing enable/disable script pairs, make both selection filters
  **identical**; never add a state filter to the "restore" side (this bug made
  re-enabling the adapter silently do nothing).
