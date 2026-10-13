---
name: windows-ai-tooling
description: Use when setting up, troubleshooting, or removing local AI image/video tooling on Windows — ComfyUI, Flux GGUF, LTX-Video, Wan, IP-Adapter, ControlNet, InstantID; diagnosing VRAM exhaustion, custom-node ImportError, blank UI, or deadlocked servers; choosing quantised models that fit small VRAM; or building lightweight cleanup/uninstall utilities with Python + tkinter.
whenToUse: User asks to install/remove ComfyUI or AI models, complains that the ComfyUI page is blank or "Reconnecting", reports VRAM/显存不足, wants a low-VRAM model choice, asks for one-click network toggles, or wants a small Windows utility/diagnostic tool.
metadata:
  version: 1.2
  author: agent
  validated_on: RTX 5070 Laptop 8GB / Windows 11 / ComfyUI 0.39.0
  repository: https://github.com/lenren9/windows-ai-toolkit
  license: MIT
---

# Windows AI tooling — setup, rescue, and small utilities

Everything below was **executed and verified on a real machine**
(RTX 5070 Laptop, 8 GB VRAM, 32 GB RAM, Windows 11 Home CN), not theory.
Models named here were downloaded and actually run end-to-end.

Source & updates: https://github.com/lenren9/windows-ai-toolkit

## 1. Model choices that fit 8 GB VRAM

Prefer quantised single-file builds. Verified-working picks:

| Purpose | File | Size | Notes |
|:---|:---|---:|:---|
| SDXL anime | `animagine-xl-3.1.safetensors` | 6.46 GB | SDXL；fp16 即可 |
| Image→video | `wan2.2_ti2v_5B_fp16.safetensors` | 9.31 GB | 5B，8 GB 友好 |
| Image→video (alt) | `ltx-video-2b-v0.9.5.safetensors` | 5.91 GB | 2B，最快；VAE 会把尺寸对齐到 32 的倍数 |
| Fast txt2img | `flux1-schnell-Q4_K_S.gguf` | 6.32 GB | **蒸馏模型，6 步 / CFG 1.0**；20 步反而不对 |
| SD1.5 base | `v1-5-pruned-emaonly-fp16.safetensors` | 1.99 GB | IP-Adapter / OpenPose 是 SD1.5 版 |
| Text encoder | `t5xxl_fp8_e4m3fn.safetensors` | 4.56 GB | Flux 和 LTX **共用**，别下两遍 |
| Companion | `clip_l.safetensors`, `ae.safetensors` | 0.23 / 0.31 GB | Flux 必需 |

GGUF 需要 `ComfyUI-GGUF`，且 **必须** 用 `UnetLoaderGGUF` 加载——
放在 `checkpoints/` 里 `CheckpointLoaderSimple` 认不出来。

Lower quantisations if OOM: Flux `Q3_K_S` 4.85 GB / `Q2_K` 3.73 GB.

## 2. VRAM — why it runs out, and the real cause

Measured numbers from the actual machine:

| State | Used / Total |
|:---|:---|
| Idle (game closed) | 1046 MB / 8151 MB |
| 永劫无间 (Naraka) running | 5614 MB / 8151 MB ← only 2.5 GB left |
| Flux GGUF 832×1216 peak | 7608 MB |
| ComfyUI idle w/ models | ~2868 MB |

**Diagnose before blaming AI.** Run `nvidia-smi` first. In one real case the
user's "显存不足" had nothing to do with AI — a game was holding 4 GB.

Causes, in the order they usually bite:
1. **Another GPU app running** (games, 3D, video decode) — biggest single factor
2. Model too large / not quantised
3. Resolution & frame count — VRAM scales ~with pixel count
4. Browser hardware acceleration + Wallpaper Engine (~600 MB combined)
5. Fragmentation / PyTorch caching allocator holding freed blocks
6. Dual-GPU laptops (iGPU + dGPU): verify the app runs on the **dGPU** via
   `Get-Counter '\GPU Process Memory(*)\Dedicated Usage'` and the adapter LUID
7. "Laggy on first load" = shader compilation — normal, not a fault

```powershell
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
Get-Counter '\GPU Process Memory(*)\Dedicated Usage'   # per-process, incl. graphics
```

## 3. ComfyUI: blank page / "Reconnecting" — the real root cause

**Symptom:** page loads (title says ComfyUI) but canvas is blank, or the UI
sits at "Reconnecting". Server process alive, CPU 0% growth, sockets in
`CLOSE_WAIT`.

**Cause:** a custom node performs a **network call with no timeout** inside
`INPUT_TYPES()` or at startup. `/object_info` calls `INPUT_TYPES()` for *every*
node, so one hanging call blocks the whole endpoint → the frontend never gets
its data → blank page.

Proven offenders:
- `ComfyUI-Manager` — fetches registry / custom-node-list from
  `raw.githubusercontent.com`
- `ComfyUI-Reactor` — `get_restorers()` → `download()` inside `INPUT_TYPES()`

Fix: move them out of `custom_nodes/`. Verify with
`curl -w '%{time_total}' http://127.0.0.1:8188/object_info` — should return
in ~0.1 s (it once took **50.4 s**).

**Also fix the browser side:** the tab was loaded while the server was
deadlocked, so its XHR/WebSocket is dangling and will *not* self-heal.
Ctrl+Shift+R, or close the tab, or use an incognito window.

## 4. Custom-node pip dependencies

Install into `python_embeded` only, and **always pin** the stack that must not
move:

```
# constraints.txt
numpy==2.5.3
torch==2.14.0+cu130
torchvision==0.29.0+cu130
```
```powershell
.\python_embeded\python.exe -m pip install -c constraints.txt <pkgs>
```

Useful groups (all verified to import on this box):
- Flux GGUF: `gguf sentencepiece protobuf`
- face/control: `opencv-python scikit-image onnxruntime insightface`
- LTX: `colour-science`
- **Do NOT install `diffusers`** — it drags torch and can break CUDA.

## 5. Downloads on a restricted network

- Blocked: `github.com`, `raw.githubusercontent.com`, `huggingface.co`
- Works: `modelscope.cn`, `hf-mirror.com`, `registry.npmmirror.com`,
  `mirrors.tuna.tsinghua.edu.cn`
- **Parallel connections stall here.** Use sequential resumable:
  `curl -L -C - -o dest --speed-limit 20480 --speed-time 60 <url>`
- ModelScope sustained ~5–11 MB/s sequential; 8-way parallel hung

## 6. Building a tiny Windows utility (Python + tkinter)

A complete cleanup/uninstall tool can be **0.03 MB** with pure stdlib —
versus 479 MB for a comparable commercial toolbox. Verified pattern:

- `tkinter` 8.6 works; use `pythonw.exe` for no console window
- Icons without Pillow: extract via .NET `System.Drawing.Icon.ExtractAssociatedIcon`
  → save PNG → `tk.PhotoImage(file=...)` (Tk 8.6 reads PNG)
- Read installed apps from the 3 `Uninstall` registry roots; read
  `DisplayIcon` / `InstallLocation` for icons and paths
- Per-process VRAM via the GPU performance counter above
- Deep uninstall = run vendor uninstaller, **then** scan for residue

### The residue-matching rule (learned the hard way)

Never match residue with a bare substring test. `"pc"` is a substring of
`"zztestapp"+"pc"+"toolkit"` — that mistake **deleted a real folder**
(`%APPDATA%\pc`) during a test.

Safe matcher:
1. normalise (lowercase, strip non-alphanumerics)
2. exact match → hit
3. reject if either side is a **generic word** (`pc app data temp tmp cache
   config users windows common program lib bin log driver update backup …`)
4. prefix match if ≥5 chars and short/long ≥ 0.40
5. substring match only if ≥6 chars and short/long ≥ 0.60

And: **scan once, show the list, delete exactly that list.** Pass an explicit
allowlist to the delete function — never re-scan at delete time.

### Other safety rules
- Every destructive action confirms first
- Clean *contents* of temp/cache dirs, never the dir itself
- Skip locked files and report them; never force-delete user documents
- Registry: list orphans, do not auto-delete
- Keep a "bystander" check in tests: assert unrelated folders survive

## 7. One-click wired/wireless network toggle

```bat
netsh interface set interface "以太网" admin=enable   :: or disable
```
Requires admin, so self-elevate:
```bat
net session >nul 2>&1 || (powershell -Command "Start-Process '%~f0' -Verb RunAs" & exit /b)
```
Prefer `Enable-NetAdapter` / `Disable-NetAdapter` with
`Where MediaType -eq '802.3'` — it auto-resolves the adapter and avoids
Chinese-name encoding problems in `.bat` (cmd reads them as GBK).

**Bug to avoid:** in an enable/disable pair, make both selection filters
**identical**. Adding `-and $_.Status -ne 'Disabled'` to the enable side made
it silently skip the very adapter it had to restore.

## 8. Environment gotchas

- PowerShell **5.1**: no `??`, no `?:` ternary; keeps failing on nested quotes
- Non-ASCII `.ps1` needs a UTF-8 **BOM** or it mis-parses
- `.bat` must stay **ASCII-only** — `"以太网"` becomes `""`
- Nested `"…"` inside Chinese strings breaks Python source; use 「」
- Always `py_compile` and import-test before claiming a script works
- When launching a GUI for verification, start it, check
  `MainWindowTitle` + `WorkingSet64`, then close it
- Network adapters on this box: wired `以太网` (Realtek 2.5GbE),
  wireless `WLAN` (MediaTek Wi-Fi 6), plus `蓝牙网络连接`
