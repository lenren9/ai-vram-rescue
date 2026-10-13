# 🧰 DSH Skills — Windows AI 工具链实战技能包

> 这不是"说明书"，是**在一台真实机器上跑通并踩过坑**的操作手册。
> 每条结论都有实测数字支撑；每个"坑"都真实发生过。

[![Validated](https://img.shields.io/badge/validated-RTX%205070%20Laptop%208GB-76B900)](#)
[![OS](https://img.shields.io/badge/OS-Windows%2011-0078D4)](#)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-0.39.0-4B8BBE)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

---

## 为什么值得一看

大多数 ComfyUI / AI 部署教程只告诉你"怎么装能跑"，而**不告诉你装完之后那些诡异的故障**：

| 你会遇到的症状 | 网上教程 | 本仓库 |
|---|---|---|
| 页面一片空白 / 一直 "Reconnecting" | 让你重装 | **指出真凶**：`INPUT_TYPES()` 里的无超时网络请求死锁主线程 |
| `显存不足` 但你没开 AI | 让你换显卡 | **教你 3 条命令定位**：真实案例是游戏占了 4 GB |
| 8 GB 显存该下哪个模型 | 列一堆 | **给出实测能跑的型号 + 体积 + 步数** |
| 下载卡在 0 MB/s | 让你换源 | **解释为什么并发会挂，串行 `curl -C -` 为什么行** |
| 卸载后注册表一堆残留 | 不处理 | **给出防误删的匹配算法**（含一次真实事故复盘） |

---

## 📦 内容

### `skills/windows-ai-tooling` ⭐ 主技能

Windows 上本地 AI 图像/视频工具链的**安装、抢救、量化选型**。

- **8 GB 显存模型对照表** — 全部实测下载并跑通
  | 用途 | 文件 | 体积 |
  |---|---|---|
  | SDXL 动漫 | `animagine-xl-3.1.safetensors` | 6.46 GB |
  | 图生视频 | `wan2.2_ti2v_5B_fp16.safetensors` | 9.31 GB |
  | 图生视频(快) | `ltx-video-2b-v0.9.5.safetensors` | 5.91 GB |
  | 快速文生图 | `flux1-schnell-Q4_K_S.gguf` | 6.32 GB |
  | SD1.5 底模 | `v1-5-pruned-emaonly-fp16.safetensors` | 1.99 GB |
  | 文本编码器 | `t5xxl_fp8_e4m3fn.safetensors` | 4.56 GB |

- **空白页故障的完整根因分析**
  ```
  症状：进程活着、CPU 0% 增长、7 个 CLOSE_WAIT 连接
  /object_info 耗时 50.4 秒  →  移除两个节点后 0.11 秒
  ```
  含精确到代码行的解释，以及"浏览器标签页为什么不会自愈"。

- **显存诊断三板斧**
  ```powershell
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv
  Get-Counter '\GPU Process Memory(*)\Dedicated Usage'   # 图形进程也能看到
  ```
  实测：空闲 1046 MB → 游戏运行时 5614 MB / 8151 MB。

- **依赖安装的正确姿势** — 必须用 `constraints.txt` 钉住
  `torch` / `numpy` / `torchvision`，否则 CUDA 被换掉。

### `skills/user-collab-style`

与"结果优先"型用户协作的规则：只给结论、不给过程流水账、
中途不打断、破坏性操作前必须确认、如何把模糊需求改写成可验收的提示词。

### `skills/web-game-dev`

Vite + TypeScript + Three.js + Capacitor 手游栈（TapTap 无版号试玩）
的完整命令集、架构约束（模块不得互相 import）、合规红线（无内购、
强制实名、几何体敌人、≤50 MB 包体）。

### `tools/pctoolkit.py` — 附赠：0.03 MB 的清理卸载工具

对比 **479 MB** 的商业工具箱，这只是它的 **0.01%**：

- 彻底卸载（卸载后深度扫残留：目录 + 注册表）
- 显存占用可视化（逐进程）
- 垃圾清理（24 类缓存，只删内容不删目录）
- 注册表残留扫描（只列不删）
- Windows 更新管理（暂停 / 清缓存 / 重置组件）
- 隐藏快捷方式小箭头（只改 HKCU，可完全还原）

纯 Python 标准库 + tkinter，**零第三方依赖**，运行内存约 39 MB。

---

## 🔥 三个真实事故复盘

### 1. `"pc"` 是 `"zztestapp"+"pc"+"toolkit"` 的子串 → 删掉了真实目录

写"残留清理"时用了任意子串匹配，结果测试中**真的删除了**
`%APPDATA%\pc` —— 一个与本软件无关的真实目录，且无法恢复。

**修复后的匹配算法**（三档 + 通用词黑名单）：
1. 规范化后完全相同 → 命中
2. 任一方是通用词（`pc app data temp cache windows …`）→ **拒绝**
3. 前缀匹配：≥5 字符且短/长 ≥ 0.40
4. 子串匹配：**≥6 字符**且短/长 ≥ 0.60

配套铁律：**扫描一次、列出清单、就删这份清单** —— 删除时绝不重新扫描。

### 2. 启用/禁用脚本不对称

`connect_net.bat` 里多写了 `-and $_.Status -ne 'Disabled'`，
于是它**跳过了那张已禁用、正需要被启用的网卡**。
能断网、但连不回来。（这个 bug 由用户发现并质疑）

**规则**：成对的启用/禁用脚本，两侧筛选条件必须**完全一致**。

### 3. 中文写进 `.bat` / `.ps1`

```
预期："以太网"      实际："浠ュお缁"
```
cmd 按 GBK 读文件，PowerShell 5.1 无 BOM 时按 ANSI 读 `.ps1`。

**规则**：`.bat` 保持纯 ASCII；`.ps1` 若含中文必须加 UTF-8 BOM；
更稳的做法是**运行时解析**（`Where MediaType -eq '802.3'`）而不是硬编码名字。

---

## 🚀 使用方式

```bash
git clone https://github.com/<you>/dsh-skills.git
cp -r dsh-skills/skills/* ~/.dsh/skills/       # 或项目内 .dsh/skills/
```

Skill 格式：`SKILL.md` + YAML frontmatter（`name` / `description` 必填）。

---

## 📋 环境基线

所有数字来自这台机器，你的结果会有差异，但**量级和因果关系是一致的**：

| | |
|---|---|
| GPU | NVIDIA RTX 5070 Laptop **8 GB** |
| iGPU | AMD Radeon 610M（双显卡混合输出） |
| RAM | 32 GB |
| OS | Windows 11 Home 中文版 |
| Compositor | dwm ~536 MB · MediaSDK_Server ~476 MB · Wallpaper Engine ~146 MB |
| 网络 | GitHub 时通时断；ModelScope / hf-mirror / npmmirror / tuna 稳定 |

---

## License

MIT — 拿去用，踩到新坑欢迎 PR 补充。
