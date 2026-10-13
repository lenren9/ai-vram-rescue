# 🧰 Windows AI Toolkit

> **在 8GB 显存的笔记本上，真正跑通本地 AI 图像/视频工具链的完整记录。**
> 不是"复制粘贴就能装"的教程——是踩过坑、有实测数字、能救急的实战手册。

[![Validated](https://img.shields.io/badge/实机验证-RTX%205070%20Laptop%208GB-76B900)](https://github.com/lenren9/windows-ai-toolkit)
[![OS](https://img.shields.io/badge/Windows-11-0078D4)](https://github.com/lenren9/windows-ai-toolkit)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-0.39.0-4B8BBE)](https://github.com/lenren9/windows-ai-toolkit)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/lenren9/windows-ai-toolkit)

---

## 🎯 为什么这个仓库不一样

大多数 AI 部署教程只写"怎么装起来"，**不写装完之后那些诡异的故障**。
这个仓库里的每一条结论，都来自一台真实机器上的**真实事故**：

| 你遇到的症状 | 常见教程 | 这里怎么做 |
|:---|:---|:---|
| 页面全白 / 一直 `Reconnecting` | 让你重装 ComfyUI | **定位真凶**：自定义节点在 `INPUT_TYPES()` 里做了无超时网络请求，`/object_info` 被拖到 **50.4 秒** → 移除后 **0.11 秒** |
| 提示"显存不足"但你没开 AI | 让你换显卡 | **先诊断再下结论**：真实案例是游戏占了 **4 GB**，AI 只分到 2.5 GB |
| 8GB 显存该下哪个模型？ | 丢一堆链接 | **给实测能跑的清单**：型号 + 体积 + 步数 + 量化等级 |
| 下载卡在 `0 MB/s` | 让你换源 | **解释原理**：并发连接会挂，串行 `curl -C -` 才稳 |
| 卸载后注册表一堆残留 | 不处理 | **给出防误删算法**（含一次真实事故复盘） |

---

## 📦 内容一览

### `skills/windows-ai-tooling` ⭐ 主技能

**8GB 显存实测能跑的模型**（全部下载并跑通过，不是纸面推荐）

| 用途 | 文件 | 体积 | 备注 |
|:---|:---|---:|:---|
| SDXL 动漫 | `animagine-xl-3.1.safetensors` | 6.46 GB | fp16 即可 |
| 图生视频 | `wan2.2_ti2v_5B_fp16.safetensors` | 9.31 GB | 5B，8GB 友好 |
| 图生视频（快） | `ltx-video-2b-v0.9.5.safetensors` | 5.91 GB | 2B，最快 |
| 快速文生图 | `flux1-schnell-Q4_K_S.gguf` | 6.32 GB | **蒸馏模型，6 步 / CFG 1.0** |
| SD1.5 底模 | `v1-5-pruned-emaonly-fp16.safetensors` | 1.99 GB | IP-Adapter / OpenPose 是 SD1.5 版 |
| 文本编码器 | `t5xxl_fp8_e4m3fn.safetensors` | 4.56 GB | **Flux 和 LTX 共用**，别下两遍 |
| 配套 | `clip_l` / `ae.safetensors` | 0.23 / 0.31 GB | Flux 必需 |

> ⚠️ 关键坑：GGUF 必须用 `UnetLoaderGGUF` 加载，放进 `checkpoints/` 里
> `CheckpointLoaderSimple` **认不出来**。

**显存诊断三板斧**
```powershell
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
Get-Counter '\GPU Process Memory(*)\Dedicated Usage'   # 连浏览器、壁纸都能看见
```
实测：空闲 1046 MB → 游戏运行时 5614 MB / 8151 MB → Flux 出图峰值 7608 MB

**依赖安装必须钉版本**——否则 pip 会把你的 CUDA 换掉：
```
# constraints.txt
numpy==2.5.3
torch==2.14.0+cu130
torchvision==0.29.0+cu130
```

### `skills/user-collab-style`
和「结果优先」型用户协作的规则：只给结论、不写流水账、中途不打断、
破坏性操作前必须确认、如何把模糊需求改写成可验收的提示词。

### `skills/web-game-dev`
Vite + TypeScript + **Three.js** + Capacitor 手游栈（TapTap 无版号试玩）：
命令集、架构约束（模块不得互相 import）、合规红线（无内购 / 强制实名 /
几何体敌人 / ≤50MB 包体）。

### `tools/pctoolkit.py` 🎁 附赠工具
**0.03 MB** 的 Windows 清理卸载工具（对比商业工具箱 479 MB = 它的 **0.01%**）：

- 彻底卸载（卸载后扫残留：目录 + 注册表）
- 显存占用可视化（逐进程）
- 垃圾清理（24 类缓存，只删内容不删目录）
- 注册表残留扫描（**只列不删**）
- Windows 更新管理（暂停 / 清缓存 / 重置组件）
- 隐藏快捷方式小箭头（只改 HKCU，可完全还原）

纯标准库 + tkinter，**零第三方依赖**，运行内存约 39 MB。

---

## 🔥 三个真实事故复盘

### 1. `"pc"` 是 `"zztestapp"+"pc"+"toolkit"` 的子串 → 删掉了真实目录

写"残留清理"时用了任意子串匹配，测试中**真的删除了** `%APPDATA%\pc`
——一个与本软件无关的真实目录，且**无法恢复**（无还原点、无卷影副本）。

**修复后的匹配算法**（三档 + 通用词黑名单）：
1. 规范化后完全相同 → 命中
2. 任一方是通用词（`pc app data temp cache windows …`）→ **拒绝**
3. 前缀匹配：≥5 字符且短/长 ≥ 0.40
4. 子串匹配：**≥6 字符**且短/长 ≥ 0.60

配套铁律：**扫描一次 → 列出清单 → 只删这份清单**（删除时绝不重新扫描）。

### 2. 启用/禁用脚本不对称 → 能断网但连不回来

`connect_net.bat` 多写了 `-and $_.Status -ne 'Disabled'`，
于是它**跳过了那张已禁用、正需要被启用的网卡**。

**规则**：成对的启用/禁用脚本，两侧筛选条件必须**完全一致**。

### 3. 中文写进 `.bat` / `.ps1`
```
预期："以太网"      实际："浠ュお缁"
```
cmd 按 GBK 读，PowerShell 5.1 无 BOM 时按 ANSI 读。

**规则**：`.bat` 保持纯 ASCII；`.ps1` 含中文必须加 UTF-8 BOM；
更稳的是**运行时解析**（`Where MediaType -eq '802.3'`）而非硬编码名字。

---

## 🚀 快速开始

### 用 Skill（推荐）
```bash
git clone https://github.com/lenren9/windows-ai-toolkit.git
cp -r windows-ai-toolkit/skills/* ~/.dsh/skills/        # 用户级
# 或
cp -r windows-ai-toolkit/skills/* <项目>/.dsh/skills/   # 项目级（优先级更高）
```
Skill 格式：`SKILL.md` + YAML frontmatter（`name` / `description` 必填）。

### 用附赠工具
```bash
python tools/pctoolkit.py        # 或 pythonw.exe 无控制台启动
```

---

## 📋 环境基线

所有数字来自这台机器。你的结果会有差异，但**量级和因果关系一致**：

| | |
|:---|:---|
| GPU | NVIDIA RTX 5070 Laptop **8 GB** |
| iGPU | AMD Radeon 610M（双显卡混合输出） |
| RAM | 32 GB |
| OS | Windows 11 Home 中文版 |
| 常驻显存占用 | dwm ~536 MB · MediaSDK_Server ~476 MB · Wallpaper Engine ~146 MB |
| 网络 | GitHub 时通时断；ModelScope / hf-mirror / npmmirror / 清华源稳定 |

---

## 🤝 贡献

踩到新坑？欢迎 PR。最想要的三类补充：
1. **其他显卡 / 显存**下的实测数据（6GB、12GB、16GB）
2. **新的故障案例**（尤其是那些"重装也治不好"的）
3. 更省显存的**模型量化组合**

---

## License

MIT — 拿去用。如果它帮你少熬了一夜，回来点个 ⭐ 就行。
