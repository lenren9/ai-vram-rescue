---
name: web-game-dev
description: Use when building, running, testing, or packaging a browser/mobile game on this machine — especially the dynamic-frontline (几何突击) project, or any Vite + TypeScript + Three.js + Capacitor stack. Covers the run/test commands, the zero-asset rule, the module contract architecture, TapTap compliance limits, and the 8GB-VRAM/network constraints of this PC.
whenToUse: User asks to make a game, add a feature to dynamic-frontline, run/dev/test/build the project, package an APK, or tune gameplay feel (aim assist, hit feedback, enemy AI, touch controls, audio).
metadata:
  version: 1.0
  author: agent
---

# Web game development on this machine

## Project: dynamic-frontline (几何突击 / Geometric Assault)

Mobile FPS for **TapTap open-play (no licence)**. Android landscape, 30 fps+ target.
Path: `D:\deepseek-harness\default-workspace\dynamic-frontline`

Stack: **Vite 6 + TypeScript 5.7 + Three.js 0.186 + Capacitor 7**.
There is **no engine with an editor** — it is a web game wrapped as an APK.

### Commands

```bash
pnpm install
pnpm dev                                  # dev server, phone can reach http://<PC-IP>:5173
pnpm build && pnpm preview --port 4173    # production build + preview
pnpm smoke http://localhost:4173/?debug=1 # 109 headless-Chromium checks
pnpm diag:ai <url>      # enemy AI: path state, avoidance, spawn validation
pnpm diag:touch <url>   # touch: deadzone scan, curve compare, fire mode, multi-touch
pnpm diag:audio <url>   # audio: synth cost, pool hit rate, BGM switch log
pnpm diag:magnet <url>  # bullet magnetism: angle/magnetism/hit
pnpm assets:shots <url> # 1280x720 store screenshots
pnpm assets:icon        # 512x512 icon
pnpm copyright          # software-copyright source document
```

`pnpm smoke` must stay green. It is the regression gate — run it after any change.

### Architecture rules (non-negotiable)

- **Modules never `import` each other's implementation.** Depend only on
  `core/contracts.ts`. Reach peers at runtime via `ctx.get('player')` and notify
  with `bus.emit(...)`. This is what keeps every module independently testable
  and swappable.
- **`src/main.ts` stays ≤ 200 lines** (currently 154). It only does four things:
  load modules, switch scenes, manage lifecycle, run the render loop.
- **All tuning numbers live in `src/core/config.ts`**, never scattered inline.
- **Zero binary assets.** Textures are drawn procedurally on a 64 px canvas;
  all 31 SFX and 3 BGM are synthesised from oscillators/noise/filters.
  `dist` is ~0.7 MB. Do not add image or audio files.
- Pool everything that spawns at runtime (enemies, bullets, effects) — no GC hitches.

### TapTap compliance (no-licence release)

Must all remain true, or the build is not shippable:

- **No payment of any kind** — no IAP, no shop, no top-up. UI must say 试玩内容不计费.
- **Forced real-name auth + anti-addiction** before entering the game.
- **No humanoid enemies** — geometry robots (capsule/box/sphere) only.
- **No gore** — kills are robot disassembly + blue sparks. No blood, no dismemberment.
- **Rewarded video only** (revive / double score), user-initiated; no interstitials.
- Package **≤ 50 MB**; ship both armeabi-v7a and arm64-v8a.

### Known gaps on this PC

`node`, `pnpm`, `git`, `java`, and the Android SDK are **not installed**.
Without node/pnpm the project cannot run at all. To produce a real APK you also
need **JDK 17 + Android SDK** — see `docs/ANDROID-INTEGRATION.md` and
`docs/ANDROID-SIGNING.md`. Ask before installing anything; do not silently
add multi-gigabyte toolchains.

## Machine constraints that shape every game decision

- **GPU: RTX 5070 Laptop, 8 GB VRAM.** Assume 8 GB ceiling for anything
  GPU-accelerated. Prefer lightweight engines (Godot) over Unreal.
- **Network: GitHub / raw.githubusercontent.com / huggingface.co are blocked.**
  Use npmmirror (`registry.npmmirror.com`), tuna, ModelScope, or hf-mirror.
  Install npm/pnpm packages with `--registry https://registry.npmmirror.com`.
- **Parallel downloads stall here.** Use sequential `curl -C -` (resumable).
- **PowerShell is 5.1** — no `??`, no `?:`. Non-ASCII `.ps1` needs a UTF-8 BOM;
  keep `.bat` files ASCII-only (cmd reads them as GBK).
- **Never let a package download from GitHub inside `INPUT_TYPES()` or startup** —
  no timeout means it deadlocks the main thread. This already broke ComfyUI.
