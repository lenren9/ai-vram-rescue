# Windows AI 工具链技能包

在一台 **RTX 5070 Laptop / 8 GB 显存 / Windows 11** 上实机验证过的
ComfyUI 部署、故障抢救与量化选型经验。

## 目录

| 路径 | 内容 |
|---|---|
| `skills/windows-ai-tooling/SKILL.md` | 主技能：8 GB 显存模型选型、空白页根因、显存诊断、依赖钉版本 |
| `skills/user-collab-style/SKILL.md` | 与"结果优先"型用户协作的规则 |
| `skills/web-game-dev/SKILL.md` | Vite + Three.js + Capacitor 手游栈与 TapTap 合规 |
| `tools/pctoolkit.py` | 附赠：0.03 MB 清理/彻底卸载工具（纯标准库） |

## 安装

```bash
cp -r skills/* ~/.dsh/skills/          # 用户级
# 或
cp -r skills/* <project>/.dsh/skills/  # 项目级（优先级更高）
```

## 核心结论速查

**8 GB 显存能跑什么**

| 用途 | 文件 | 体积 |
|---|---|---|
| SDXL 动漫 | animagine-xl-3.1 | 6.46 GB |
| 图生视频 | wan2.2_ti2v_5B_fp16 | 9.31 GB |
| 图生视频(快) | ltx-video-2b-v0.9.5 | 5.91 GB |
| 快速文生图 | flux1-schnell-Q4_K_S.gguf | 6.32 GB |

**ComfyUI 空白页真凶**：自定义节点在 `INPUT_TYPES()` 里做无超时网络请求。
`/object_info` 从 50.4 秒 → 0.11 秒（移除 ComfyUI-Manager / Reactor）。

**显存被谁吃了**
```powershell
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
Get-Counter '\GPU Process Memory(*)\Dedicated Usage'
```
实测：空闲 1046 MB，游戏运行时 5614 MB / 8151 MB。

**下载总卡住**：并发连接会挂，改用串行可续传
```bash
curl -L -C - -o dest --speed-limit 20480 --speed-time 60 <url>
```

## 三个真实事故

1. **`"pc"` 子串匹配删掉了真实目录** `%APPDATA%\pc` → 改用"通用词黑名单 +
   长度/比例门槛"，并坚持"扫描一次、只删清单"。
2. **启用/禁用脚本不对称** → 能断网但连不回来。
3. **中文写进 `.bat`** → `"以太网"` 变 `"浠ュお缁"`，保持 ASCII 或运行时解析。

## License

MIT
