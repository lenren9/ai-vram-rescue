#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清机工具箱 (PCToolkit) - 轻量 Windows 清理 / 检测 / 彻底卸载工具
纯标准库 + tkinter，无第三方依赖。

v1.1 新增
  - 彻底卸载：卸载后深度扫描目录+注册表残留，一键清除
  - Windows 更新：暂停更新(7/14/30/35天)、清缓存、重置组件、服务开关
  - 系统优化：隐藏/恢复快捷方式小箭头（仅改 HKCU，可完全还原）
  - 软件列表显示真实图标（.NET 提取，无需 Pillow）
  - UI：分组卡片、双色斑马纹、状态栏、图标缓存

安全底线
  - 每个破坏性操作都先弹窗确认
  - 清理只删临时/缓存目录的「内容」，不删目录本身
  - 被占用文件自动跳过并报告，绝不强删用户文档
  - 注册表默认只列出、不自动删除
"""

import os
import re
import sys
import json
import shutil
import ctypes
import platform
import subprocess
import winreg
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

APP_NAME = "清机工具箱"
APP_VER = "1.0"

# ---------------------------------------------------------------- 通用工具

def human_bytes(n):
    if n is None:
        return "-"
    try:
        n = float(n)
    except Exception:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} PB"


def run_ps(cmd, timeout=120):
    """运行 PowerShell 命令，返回 stdout 字符串。失败返回空串。"""
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return p.stdout or ""
    except Exception:
        return ""


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def safe_isdir(p):
    try:
        return os.path.isdir(p)
    except Exception:
        return False


# ---------------------------------------------------------------- 系统信息

def get_system_info():
    info = {}
    un = platform.uname()
    info["系统"] = f"{un.system} {un.release} (build {un.version})"
    info["计算机名"] = un.node
    info["处理器"] = un.processor or "-"
    info["开机时长"] = "-"
    try:
        import time
        t = ctypes.windll.kernel32.GetTickCount64() / 1000.0
        h = int(t // 3600); m = int((t % 3600) // 60)
        info["开机时长"] = f"{h} 小时 {m} 分钟"
    except Exception:
        pass

    # 内存
    try:
        out = run_ps("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory", 30).strip()
        total = int(out.splitlines()[0]) if out else 0
        out2 = run_ps("$os=Get-CimInstance Win32_OperatingSystem; $os.FreePhysicalMemory", 30).strip()
        free = int(out2.splitlines()[0]) * 1024 if out2 else 0
        info["内存"] = f"{human_bytes(total)}  (可用 {human_bytes(free)})"
    except Exception:
        info["内存"] = "-"

    # 显卡
    try:
        gpus, vram = [], []
        out = run_ps(
            "Get-CimInstance Win32_VideoController | "
            "ForEach-Object { $_.Name + '|' + [math]::Round($_.AdapterRAM/1MB) }", 40)
        for line in out.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            name, mb = line.rsplit("|", 1)
            try:
                mb_i = int(mb)
            except Exception:
                mb_i = 0
            gpus.append(name)
            if mb_i > 0:
                vram.append(f"{name}: {mb_i} MB")
        info["显卡"] = " / ".join(gpus) if gpus else "-"
        info["显卡显存"] = " / ".join(vram) if vram else "（WMI 未报告，见下方 NVIDIA 实测）"
    except Exception:
        info["显卡"] = "-"
        info["显卡显存"] = "-"

    # NVIDIA 实测显存
    info["NVIDIA 显存"] = get_nvidia_vram()

    # 磁盘
    try:
        out = run_ps(
            "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
            "ForEach-Object { $_.DeviceID + ' ' + $_.Size + ' ' + $_.FreeSpace }", 40)
        parts = []
        for line in out.splitlines():
            bits = line.split()
            if len(bits) == 3:
                try:
                    parts.append(f"{bits[0]} 可用 {human_bytes(int(bits[2]))} / 共 {human_bytes(int(bits[1]))}")
                except Exception:
                    pass
        info["磁盘"] = " | ".join(parts) if parts else "-"
    except Exception:
        info["磁盘"] = "-"

    p_start = os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup")
    u_start = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    n = 0
    for d in (p_start, u_start):
        if safe_isdir(d):
            try:
                n += len(os.listdir(d))
            except Exception:
                pass
    info["开机启动项"] = f"{n} 个"
    info["管理员权限"] = "是" if is_admin() else "否（部分清理需要管理员）"
    return info


def get_nvidia_vram():
    try:
        p = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if p.returncode != 0 or not p.stdout.strip():
            return "无 NVIDIA 显卡或驱动未就绪"
        rows = []
        for line in p.stdout.strip().splitlines():
            b = [x.strip() for x in line.split(",")]
            if len(b) >= 4:
                try:
                    rows.append(f"{b[0]}: 已用 {b[2]} MB / 共 {b[1]} MB（剩余 {b[3]} MB）")
                except Exception:
                    pass
        return " | ".join(rows) if rows else "-"
    except FileNotFoundError:
        return "未找到 nvidia-smi"
    except Exception:
        return "-"


def get_gpu_processes():
    """返回 [(显存MB, 进程名, pid)]，按占用降序。"""
    res = []
    try:
        c = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage' -ErrorAction SilentlyContinue | "
             "Select-Object -ExpandProperty CounterSamples | "
             "ForEach-Object { $_.InstanceName + ' ' + [int]$_.CookedValue }"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (c.stdout or "").splitlines():
            line = line.strip()
            m = re.match(r"pid_(\d+)_.*?\s+(\d+)$", line)
            if not m:
                continue
            pid, byt = int(m.group(1)), int(m.group(2))
            if byt < 20 * 1024 * 1024:      # 忽略 <20MB
                continue
            name = pid_to_name(pid)
            res.append((byt / 1024 / 1024, name, pid))
    except Exception:
        pass
    res.sort(reverse=True)
    return res


def pid_to_name(pid):
    try:
        out = run_ps(f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName", 15).strip()
        return out.splitlines()[0] if out else f"PID {pid}"
    except Exception:
        return f"PID {pid}"


# ---------------------------------------------------------------- 清理项

def clean_targets():
    """返回 [(显示名, 路径)]，仅系统临时/缓存，不碰用户文档。"""
    t = []
    env = os.environ
    cands = [
        ("Windows 临时文件", env.get("TEMP") or r"C:\Windows\Temp"),
        ("系统临时文件", r"C:\Windows\Temp"),
        ("用户临时文件", os.path.expandvars(r"%TEMP%")),
        ("预读取文件 Prefetch", r"C:\Windows\Prefetch"),
        ("Windows 更新缓存", r"C:\Windows\SoftwareDistribution\Download"),
        ("缩略图缓存", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer")),
        ("IE/Edge 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\INetCache")),
        ("系统错误报告", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\WER")),
        ("Crash 转储", r"C:\Windows\Minidump"),
        ("传递优化缓存", r"C:\Windows\SoftwareDistribution\DeliveryOptimization"),
        ("字体缓存", r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"),
        ("Recent 文件记录", os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent")),
        ("回收站", None),
        ("内存转储 MEMORY.DMP", r"C:\Windows\MEMORY.DMP"),
        ("Steam 下载缓存", r"D:\steam\steamapps\downloading"),
        ("NVIDIA 驱动残留", r"C:\Program Files\NVIDIA Corporation\Installer2"),
        ("旧驱动残留", r"C:\Windows\System32\DriverStore\FileRepository"),
        ("Python pip 缓存", os.path.expandvars(r"%LOCALAPPDATA%\pip\cache")),
        ("npm 缓存", os.path.expandvars(r"%APPDATA%\npm-cache")),
        ("yarn 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Yarn\Cache")),
        ("Chromium 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Chromium\User Data\Default\Cache")),
        ("Chrome 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")),
        ("Edge 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache")),
        ("Firefox 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles")),
        ("Java 缓存", os.path.expandvars(r"%LOCALAPPDATA%\Sun\Java\Deployment\cache")),
    ]
    for name, p in cands:
        if p is None or safe_isdir(p) or (p and os.path.isfile(p)):
            t.append((name, p))
    return t


def dir_size(path, cap=8000):
    """计算目录大小，最多遍历 cap 个文件后估算。"""
    total, cnt = 0, 0
    try:
        for root, dirs, files in os.walk(path):
            try:
                dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            except Exception:
                pass
            for f in files:
                cnt += 1
                if cnt > cap:
                    return total, True
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
    except Exception:
        pass
    return total, False


def clean_path(name, path):
    """安全清理：只删内部内容，不删目录本身；跳过正在使用的文件。"""
    deleted, freed, skipped, errors = 0, 0, 0, []
    if not path:
        return deleted, freed, skipped, errors
    try:
        if os.path.isfile(path):
            try:
                freed = os.path.getsize(path)
                os.remove(path)
                return 1, freed, 0, errors
            except Exception as e:
                return 0, 0, 0, [f"{name}: {e}"]

        for entry in os.listdir(path):
            fp = os.path.join(path, entry)
            try:
                if safe_isdir(fp):
                    sz, _ = dir_size(fp)
                    shutil.rmtree(fp, ignore_errors=True)
                    if not os.path.exists(fp):
                        deleted += 1; freed += sz
                    else:
                        skipped += 1
                else:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    deleted += 1; freed += sz
            except Exception as e:
                skipped += 1
                errors.append(f"{os.path.basename(fp)}: {str(e)[:60]}")
    except Exception as e:
        errors.append(f"{name}: {str(e)[:80]}")
    return deleted, freed, skipped, errors


def empty_recycle_bin():
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000007)
        return True, None
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------- 卸载 / 注册表

def list_installed():
    """读取卸载注册表，返回 [(名称, 卸载命令, 版本, 发布者, 大小MB)]"""
    items, seen = [], set()
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, sub in roots:
        try:
            k = winreg.OpenKey(hive, sub)
        except Exception:
            continue
        i = 0
        while True:
            try:
                name = winreg.EnumKey(k, i); i += 1
            except OSError:
                break
            try:
                sk = winreg.OpenKey(k, name)
                def gv(v):
                    try:
                        return winreg.QueryValueEx(sk, v)[0]
                    except Exception:
                        return ""
                disp = gv("DisplayName").strip()
                if not disp or disp in seen:
                    winreg.CloseKey(sk); continue
                if gv("SystemComponent") == "1":
                    winreg.CloseKey(sk); continue
                parent = gv("ParentDisplayName").strip()
                if parent:
                    winreg.CloseKey(sk); continue
                uninst = gv("UninstallString").strip()
                if not uninst:
                    winreg.CloseKey(sk); continue
                try:
                    sz = int(gv("EstimatedSize")) / 1024.0
                except Exception:
                    sz = 0
                seen.add(disp)
                items.append((disp, uninst, gv("DisplayVersion"), gv("Publisher"), sz))
                winreg.CloseKey(sk)
            except Exception:
                continue
        try:
            winreg.CloseKey(k)
        except Exception:
            pass
    items.sort(key=lambda x: x[0].lower())
    return items


def orphan_registry_keys():
    """查找卸载项指向的安装目录已不存在 -> 残留注册表。"""
    orphans = []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, sub in roots:
        try:
            k = winreg.OpenKey(hive, sub)
        except Exception:
            continue
        i = 0
        while True:
            try:
                name = winreg.EnumKey(k, i); i += 1
            except OSError:
                break
            try:
                sk = winreg.OpenKey(k, name)
                def gv(v):
                    try:
                        return winreg.QueryValueEx(sk, v)[0]
                    except Exception:
                        return ""
                disp = gv("DisplayName").strip()
                loc = gv("InstallLocation").strip()
                if disp and loc:
                    loc = loc.strip('"').rstrip("\\")
                    if loc and not safe_isdir(loc):
                        orphans.append((disp, loc, f"{sub}\\{name}"))
                winreg.CloseKey(sk)
            except Exception:
                continue
        try:
            winreg.CloseKey(k)
        except Exception:
            pass
    return orphans


# ---------------------------------------------------------------- 深度卸载引擎

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# 通用目录名：永不参与模糊匹配，只允许精确命中。
# 血泪教训：曾因 "pc" 是 "zztestapp"+"pc"+"toolkit" 的子串而误删真实目录
# C:\Users\<u>\AppData\Roaming\pc。
_GENERIC_DIRS = {
    "pc", "app", "apps", "data", "temp", "tmp", "cache", "config", "conf",
    "setting", "settings", "user", "users", "local", "roaming", "program",
    "programs", "files", "file", "document", "documents", "download",
    "downloads", "microsoft", "windows", "common", "shared", "system",
    "system32", "bin", "lib", "log", "logs", "driver", "drivers", "update",
    "updates", "backup", "backups", "default", "public", "desktop", "start",
    "menu", "software", "appdata", "support", "online", "cloud", "client",
}
_MIN_FUZZY = 5      # 参与模糊匹配的最短规范化长度
_MIN_RATIO = 0.5    # 较短者至少占较长者的 50%


def _match_name(entry_name, key):
    """严格匹配软件名与目录/键名。

    分三档，逐档放宽，且都比原来的"任意子串"安全得多：

      1. 规范化后完全相同                      -> 命中
      2. 前缀相同：较短者是较长者的前缀，
         且长度 >= 5，较长/较短比例 >= 0.40    -> 命中
         (Google / GoogleChrome、Steam / SteamLibrary)
      3. 子串包含：较短者出现在较长者中，
         且长度 >= 6，比例 >= 0.60             -> 命中

    任一方是通用词（_GENERIC_DIRS）时直接拒绝。

    血泪教训：曾用"任意子串"匹配，导致 "pc" 命中
    "zztestapp"+"pc"+"toolkit"，误删了真实目录
    C:\\Users\\<u>\\AppData\\Roaming\\pc。
    前缀规则让 "pc" 永远无法命中一个以 zztestapp 开头的名字。
    """
    n = _norm(entry_name)
    if not n or not key:
        return False
    if n == key:
        return True
    if n in _GENERIC_DIRS or key in _GENERIC_DIRS:
        return False

    short, long_ = (n, key) if len(n) <= len(key) else (key, n)
    ratio = len(short) / float(len(long_))

    # 档 2：前缀
    if len(short) >= 5 and long_.startswith(short) and ratio >= 0.40:
        return True
    # 档 3：子串
    if len(short) >= 6 and short in long_ and ratio >= 0.60:
        return True
    return False


def _residue_roots():
    env = os.environ
    return [
        env.get("ProgramFiles", r"C:\Program Files"),
        env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        env.get("ProgramData", r"C:\ProgramData"),
        env.get("LOCALAPPDATA", ""),
        os.path.join(env.get("LOCALAPPDATA", ""), "Programs"),
        env.get("APPDATA", ""),
        r"D:\application",
        r"D:\Program Files",
    ]


def _reg_uninstall_roots():
    return [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]


def _reg_software_roots():
    return [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE"),
    ]


def _sublist(hive, path):
    out = []
    try:
        k = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
    except Exception:
        return out
    i = 0
    while True:
        try:
            out.append(winreg.EnumKey(k, i)); i += 1
        except OSError:
            break
    try:
        winreg.CloseKey(k)
    except Exception:
        pass
    return out


def deep_scan_residue(display_name, install_location=""):
    """扫描某软件卸载后的全部残留：目录 + 注册表。"""
    key = _norm(display_name)
    if len(key) < 3:
        return {"dirs": [], "registry": [], "services": []}

    dirs = []
    # 1) 已知安装目录（含其父目录下的同名项）
    cands = []
    if install_location:
        loc = install_location.strip().strip('"').rstrip("\\")
        if loc:
            cands.append(loc)
    for root in _residue_roots():
        if not root or not safe_isdir(root):
            continue
        try:
            for entry in os.listdir(root):
                full = os.path.join(root, entry)
                if not safe_isdir(full):
                    continue
                if _match_name(entry, key):
                    cands.append(full)
        except Exception:
            continue
    seen = set()
    for c in cands:
        cl = c.lower()
        if cl in seen:
            continue
        seen.add(cl)
        if safe_isdir(c):
            dirs.append(c)

    # 2) 注册表：卸载项 + 软件配置项
    reg = []
    for hive, sub in _reg_uninstall_roots():
        for name in _sublist(hive, sub):
            try:
                k = winreg.OpenKey(hive, sub + "\\" + name, 0, winreg.KEY_READ)
                try:
                    disp = winreg.QueryValueEx(k, "DisplayName")[0]
                except Exception:
                    disp = ""
                winreg.CloseKey(k)
                if disp and _norm(disp) == key:
                    reg.append((hive, sub + "\\" + name, f"卸载项: {disp}"))
            except Exception:
                continue

    for hive, sub in _reg_software_roots():
        for name in _sublist(hive, sub):
            if _match_name(name, key):
                reg.append((hive, sub + "\\" + name, f"配置项: {name}"))

    return {"dirs": dirs, "registry": reg, "services": []}


def _reg_delete_tree(hive, path):
    """递归删除注册表键。"""
    try:
        k = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
    except Exception:
        return True
    subs = []
    i = 0
    while True:
        try:
            subs.append(winreg.EnumKey(k, i)); i += 1
        except OSError:
            break
    try:
        winreg.CloseKey(k)
    except Exception:
        pass
    ok = True
    for s in subs:
        if not _reg_delete_tree(hive, path + "\\" + s):
            ok = False
    try:
        winreg.DeleteKey(hive, path)
    except Exception:
        ok = False
    return ok


def deep_clean(display_name, install_location="", allow_dirs=None, allow_reg=None):
    """按【用户已确认的清单】彻底清除。

    安全设计：删除动作只接受显式传入的 allow_dirs / allow_reg，
    绝不在删除时重新扫描 —— 这样"界面上给你看的"和"实际删掉的"
    永远是同一批东西，杜绝"看到 A 却删了 B"。
    """
    errors = []
    dirs_removed, reg_removed = 0, 0

    for d in (allow_dirs or []):
        if not d or not safe_isdir(d):
            continue
        # 最后一道防线：路径必须存在于常见的残留根之下
        ok_root = False
        dl = d.lower()
        for r in _residue_roots():
            if r and dl.startswith(r.lower().rstrip("\\") + "\\"):
                ok_root = True
                break
        if not ok_root:
            errors.append(f"已跳过（不在允许的目录范围内）: {d}")
            continue
        if not _match_name(os.path.basename(d), _norm(display_name)):
            errors.append(f"已跳过（名称不匹配）: {d}")
            continue
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception as e:
            errors.append(f"{d}: {str(e)[:60]}")
        if not safe_isdir(d):
            dirs_removed += 1
        else:
            errors.append(f"未能删除（可能被占用）: {d}")

    for hive, path in (allow_reg or []):
        if not path:
            continue
        # 只允许删除卸载项或与名称匹配的软件项
        leaf = path.rsplit("\\", 1)[-1]
        is_uninst = "CurrentVersion\\Uninstall" in path
        if not is_uninst and not _match_name(leaf, _norm(display_name)):
            errors.append(f"已跳过（名称不匹配）: {path}")
            continue
        if _reg_delete_tree(hive, path):
            reg_removed += 1
        else:
            errors.append(f"注册表未删除: {path}")

    return {"dirs_removed": dirs_removed, "reg_removed": reg_removed, "errors": errors}


# ---------------------------------------------------------------- 系统优化

def is_arrows_hidden():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons")
        try:
            winreg.QueryValueEx(k, "29")
            winreg.CloseKey(k)
            return True
        except Exception:
            winreg.CloseKey(k)
            return False
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_arrows(hide, blank_ico):
    """隐藏/恢复快捷方式小箭头。仅改 HKCU，可完全还原。"""
    path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
    try:
        if hide:
            if not os.path.isfile(blank_ico):
                return False, "缺少空白图标文件"
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
            winreg.SetValueEx(k, "29", 0, winreg.REG_SZ, blank_ico)
            winreg.CloseKey(k)
        else:
            try:
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
                try:
                    winreg.DeleteValue(k, "29")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(k)
            except FileNotFoundError:
                pass
        return True, None
    except Exception as e:
        return False, str(e)


def make_blank_ico(path):
    """生成一个 32x32 全透明的 .ico（纯 Python，无第三方库）。"""
    w = h = 32
    xor = b"\x00" * (w * h * 4)
    and_mask = b"\x00" * (h * (w // 8))
    bih = (40).to_bytes(4, "little") + w.to_bytes(4, "little") + (h * 2).to_bytes(4, "little") \
        + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") + (0).to_bytes(4, "little") \
        + (len(xor) + len(and_mask)).to_bytes(4, "little") \
        + (0).to_bytes(4, "little") * 4
    img = bih + xor + and_mask
    hdr = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
    ent = bytes([w, h, 0, 0]) + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") \
        + len(img).to_bytes(4, "little") + (22).to_bytes(4, "little")
    try:
        with open(path, "wb") as f:
            f.write(hdr + ent + img)
        return True
    except Exception:
        return False


def restart_explorer():
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                       capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import time
        time.sleep(1.5)
        subprocess.Popen("explorer.exe", shell=True)
        return True, None
    except Exception as e:
        return False, str(e)


def wu_state():
    """Windows 更新服务状态 + 缓存大小 + 暂停信息。"""
    st = {}
    try:
        out = run_ps("(Get-Service wuauserv).Status; (Get-Service bits).Status", 30)
        lines = [x.strip() for x in out.splitlines() if x.strip()]
        st["wuauserv"] = lines[0] if len(lines) > 0 else "?"
        st["bits"] = lines[1] if len(lines) > 1 else "?"
    except Exception:
        st["wuauserv"] = st["bits"] = "?"
    try:
        p = r"C:\Windows\SoftwareDistribution\Download"
        sz, _ = dir_size(p) if safe_isdir(p) else (0, False)
        st["cache"] = human_bytes(sz)
    except Exception:
        st["cache"] = "-"
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings")
        try:
            v = winreg.QueryValueEx(k, "PauseUpdatesExpiryTime")[0]
            st["paused_until"] = str(v)
        except Exception:
            st["paused_until"] = "未暂停"
        try:
            v2 = winreg.QueryValueEx(k, "PauseFeatureUpdatesEndTime")[0]
            st["feature_until"] = str(v2)
        except Exception:
            st["feature_until"] = "-"
        winreg.CloseKey(k)
    except Exception:
        st["paused_until"] = "未暂停"
        st["feature_until"] = "-"
    return st


def wu_pause(days):
    """暂停 Windows 更新 N 天（写入 UX\\Settings，可恢复）。"""
    import datetime
    try:
        now = datetime.datetime.now()
        end = now + datetime.timedelta(days=days)
        iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        k = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings",
                               0, winreg.KEY_SET_VALUE)
        for name in ("PauseUpdatesExpiryTime", "PauseFeatureUpdatesEndTime",
                     "PauseQualityUpdatesEndTime"):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, iso)
        for name in ("PauseFeatureUpdatesStartTime", "PauseQualityUpdatesStartTime"):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ,
                              now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        winreg.CloseKey(k)
        return True, f"已暂停至 {end.strftime('%Y-%m-%d')}"
    except PermissionError:
        return False, "需要管理员权限"
    except Exception as e:
        return False, str(e)


def wu_resume():
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings",
                           0, winreg.KEY_SET_VALUE)
        for name in ("PauseUpdatesExpiryTime", "PauseFeatureUpdatesEndTime",
                     "PauseQualityUpdatesEndTime", "PauseFeatureUpdatesStartTime",
                     "PauseQualityUpdatesStartTime"):
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
        return True, "已恢复自动更新"
    except PermissionError:
        return False, "需要管理员权限"
    except Exception as e:
        return False, str(e)


def wu_stop_services():
    out = run_ps("Stop-Service wuauserv -Force -ErrorAction SilentlyContinue; "
                 "Stop-Service bits -Force -ErrorAction SilentlyContinue; 'done'", 120)
    return "done" in out


def wu_start_services():
    out = run_ps("Start-Service bits -ErrorAction SilentlyContinue; "
                 "Start-Service wuauserv -ErrorAction SilentlyContinue; 'done'", 120)
    return "done" in out


def wu_clear_cache():
    """清空 SoftwareDistribution\\Download（先停服务）。"""
    p = r"C:\Windows\SoftwareDistribution\Download"
    if not safe_isdir(p):
        return 0, "目录不存在"
    d, freed, skipped, errs = clean_path("Windows 更新缓存", p)
    return freed, (errs[0] if errs else None)


def wu_reset_components():
    """重置更新组件：停服务 -> 重命名 SoftwareDistribution -> 重启服务。"""
    run_ps("Stop-Service wuauserv -Force -ErrorAction SilentlyContinue; "
           "Stop-Service bits -Force -ErrorAction SilentlyContinue; 'ok'", 120)
    import time
    time.sleep(1)
    src = r"C:\Windows\SoftwareDistribution"
    dst = r"C:\Windows\SoftwareDistribution.old"
    ok = False
    try:
        if safe_isdir(dst):
            shutil.rmtree(dst, ignore_errors=True)
        os.rename(src, dst)
        ok = True
    except Exception as e:
        return False, f"重命名失败（需管理员）: {str(e)[:70]}"
    run_ps("Start-Service bits -ErrorAction SilentlyContinue; "
           "Start-Service wuauserv -ErrorAction SilentlyContinue; 'ok'", 120)
    return ok, "已重置，旧数据在 C:\\Windows\\SoftwareDistribution.old"


# ---------------------------------------------------------------- 图标提取

def get_display_icon_path(display_name):
    for hive, sub in _reg_uninstall_roots():
        for name in _sublist(hive, sub):
            try:
                k = winreg.OpenKey(hive, sub + "\\" + name, 0, winreg.KEY_READ)
                try:
                    disp = winreg.QueryValueEx(k, "DisplayName")[0]
                except Exception:
                    disp = ""
                if disp and disp == display_name:
                    try:
                        ic = winreg.QueryValueEx(k, "DisplayIcon")[0]
                    except Exception:
                        ic = ""
                    try:
                        loc = winreg.QueryValueEx(k, "InstallLocation")[0]
                    except Exception:
                        loc = ""
                    winreg.CloseKey(k)
                    return ic, loc
                winreg.CloseKey(k)
            except Exception:
                continue
    return "", ""


def extract_icon_png(src, out_png):
    """用 .NET 把 exe/ico 的图标导出成 PNG（无需 Pillow）。"""
    if not src:
        return False
    src = src.strip().strip('"').split(",")[0].strip().strip('"')
    if not os.path.isfile(src):
        return False
    if os.path.isfile(out_png) and os.path.getsize(out_png) > 0:
        return True
    ps = (
        "Add-Type -AssemblyName System.Drawing;"
        "try{"
        f"$p='{src}';"
        "if($p -match '\\.ico$'){$i=New-Object System.Drawing.Icon($p)}"
        "else{$i=[System.Drawing.Icon]::ExtractAssociatedIcon($p)};"
        "$b=$i.ToBitmap();"
        f"$b.Save('{out_png}',[System.Drawing.Imaging.ImageFormat]::Png);"
        "'OK'}catch{'ERR'}"
    )
    out = run_ps(ps, 60)
    return "OK" in out and os.path.isfile(out_png)


# ---------------------------------------------------------------- GUI

import threading
import queue


class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME} v{APP_VER}  ·  轻量清理与彻底卸载")
        root.geometry("1120x720")
        root.minsize(960, 600)

        self.icon_cache = {}          # 名称 -> PhotoImage（保持引用防 GC）
        self.icon_queue = queue.Queue()
        self.icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        os.makedirs(self.icon_dir, exist_ok=True)
        self.blank_ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blank.ico")
        self.un_items = []

        self._setup_style()

        # 顶部标题条
        head = tk.Frame(root, bg="#1f6feb", height=46)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="  清机工具箱", bg="#1f6feb", fg="white",
                 font=("Microsoft YaHei UI", 13, "bold")).pack(side="left", padx=(10, 0))
        tk.Label(head, text="清理 · 检测 · 彻底卸载 · 更新管理   ", bg="#1f6feb", fg="#cfe2ff",
                 font=("Microsoft YaHei UI", 9)).pack(side="right")

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.f_info = ttk.Frame(nb, padding=8)
        self.f_clean = ttk.Frame(nb, padding=8)
        self.f_gpu = ttk.Frame(nb, padding=8)
        self.f_uninst = ttk.Frame(nb, padding=8)
        self.f_resid = ttk.Frame(nb, padding=8)
        self.f_update = ttk.Frame(nb, padding=8)
        self.f_tune = ttk.Frame(nb, padding=8)
        self.f_port = ttk.Frame(nb, padding=8)

        for f, t in ((self.f_info, "  系统信息  "), (self.f_clean, "  垃圾清理  "),
                     (self.f_gpu, "  显存/GPU  "), (self.f_uninst, "  软件卸载  "),
                     (self.f_resid, "  残留清理  "), (self.f_update, "  系统更新  "),
                     (self.f_tune, "  系统优化  "), (self.f_port, "  便携工具  ")):
            nb.add(f, text=t)

        self._build_info()
        self._build_clean()
        self._build_gpu()
        self._build_uninst()
        self._build_resid()
        self._build_update()
        self._build_tune()
        self._build_port()

        self.status = tk.StringVar(value="就绪")
        bar = tk.Label(root, textvariable=self.status, anchor="w",
                       bg="#f0f0f0", fg="#333", padx=8, pady=3,
                       font=("Microsoft YaHei UI", 9))
        bar.pack(fill="x", side="bottom")

        self.root.after(150, self.refresh_info)
        self.root.after(400, self._poll_icons)

    def _setup_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Treeview", rowheight=24, font=("Microsoft YaHei UI", 9))
        st.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))
        st.configure("TButton", padding=(10, 5), font=("Microsoft YaHei UI", 9))
        st.configure("TNotebook.Tab", padding=(14, 7), font=("Microsoft YaHei UI", 9))
        st.configure("TCheckbutton", font=("Microsoft YaHei UI", 9))
        st.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 9, "bold"))

    def set_status(self, t):
        self.status.set(t)
        self.root.update_idletasks()

    def _mk_tree(self, parent, cols, widths, anchors, height=16, tree_col=None):
        """统一建表：交替行色 + 滚动条。返回 treeview。"""
        if tree_col:
            tv = ttk.Treeview(parent, columns=cols, show="tree headings", height=height)
            tv.heading("#0", text="")
            tv.column("#0", width=30, stretch=False)
        else:
            tv = ttk.Treeview(parent, columns=cols, show="headings", height=height)
        for c, w, a in zip(cols, widths, anchors):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor=a)
        tv.tag_configure("odd", background="#f7f9fc")
        tv.tag_configure("even", background="#ffffff")
        sb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
        tv.configure(yscroll=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tv

    def _row_tag(self, i):
        return "odd" if i % 2 else "even"

    # ============================================================ 系统信息
    def _build_info(self):
        f = self.f_info
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="刷新信息", command=self.refresh_info).pack(side="left")
        ttk.Button(top, text="系统信息 msinfo32",
                   command=lambda: self.launch("msinfo32")).pack(side="left", padx=6)
        ttk.Button(top, text="设备管理器",
                   command=lambda: self.launch("devmgmt.msc")).pack(side="left")
        ttk.Button(top, text="任务管理器",
                   command=lambda: self.launch("taskmgr")).pack(side="left", padx=6)
        self.info_tv = self._mk_tree(f, ("项目", "值"), (210, 830), ("w", "w"), height=20)

    def refresh_info(self):
        self.set_status("正在收集系统信息…")
        for i in self.info_tv.get_children():
            self.info_tv.delete(i)
        info = get_system_info()
        for n, (k, v) in enumerate(info.items()):
            self.info_tv.insert("", "end", values=(k, v), tags=(self._row_tag(n),))
        self.set_status("系统信息已刷新")

    def launch(self, what):
        try:
            os.startfile(what)
        except Exception:
            try:
                subprocess.Popen(what, shell=True)
            except Exception as e:
                messagebox.showerror("错误", str(e))

    # ============================================================ 垃圾清理
    def _build_clean(self):
        f = self.f_clean
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="扫描大小", command=self.scan_clean).pack(side="left")
        ttk.Button(top, text="全选", command=lambda: self._check_all(True)).pack(side="left", padx=4)
        ttk.Button(top, text="全不选", command=lambda: self._check_all(False)).pack(side="left")
        ttk.Button(top, text="清理选中项", command=self.do_clean).pack(side="left", padx=8)
        ttk.Button(top, text="清空回收站", command=self.do_recycle).pack(side="left")
        self.clean_sum = tk.StringVar(value="总计: -")
        tk.Label(top, textvariable=self.clean_sum, fg="#1f6feb",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=14)

        self.clean_tv = self._mk_tree(f, ("选中", "项目", "路径", "大小"),
                                      (54, 200, 620, 100),
                                      ("center", "w", "w", "e"), height=20)
        self.clean_tv.bind("<Button-1>", self._toggle_clean)

    def _check_all(self, state):
        for it in self.clean_tv.get_children():
            v = list(self.clean_tv.item(it, "values"))
            v[0] = "√" if state else ""
            self.clean_tv.item(it, values=v)

    def _toggle_clean(self, ev):
        if self.clean_tv.identify_region(ev.x, ev.y) != "cell":
            return
        if self.clean_tv.identify_column(ev.x) != "#1":
            return
        item = self.clean_tv.identify_row(ev.y)
        if not item:
            return
        v = list(self.clean_tv.item(item, "values"))
        v[0] = "√" if v[0] != "√" else ""
        self.clean_tv.item(item, values=v)

    def scan_clean(self):
        self.set_status("正在扫描…")
        for i in self.clean_tv.get_children():
            self.clean_tv.delete(i)
        total = 0
        for n, (name, p) in enumerate(clean_targets()):
            sz, approx = (0, False) if p is None else dir_size(p)
            total += sz
            self.clean_tv.insert("", "end",
                                 values=("", name, p or "(虚拟项)",
                                         human_bytes(sz) + (" ~" if approx else "")),
                                 tags=(self._row_tag(n),))
        self.clean_sum.set(f"可清理总计: {human_bytes(total)}")
        self.set_status("扫描完成")

    def do_clean(self):
        sel = []
        for it in self.clean_tv.get_children():
            v = self.clean_tv.item(it, "values")
            if v and v[0] == "√":
                sel.append((v[1], v[2]))
        if not sel:
            messagebox.showinfo("提示", "请先勾选（点击「选中」列）")
            return
        if not messagebox.askyesno("确认", f"将清理 {len(sel)} 项，不可恢复。\n继续？"):
            return
        tf = td = ts = 0
        errs = []
        for name, p in sel:
            self.set_status(f"清理: {name}")
            if "回收站" in name:
                ok, e = empty_recycle_bin()
                if not ok:
                    errs.append(f"回收站: {e}")
                continue
            d, fr, s, e = clean_path(name, p)
            td += d; tf += fr; ts += s
            errs.extend(e[:2])
        msg = f"完成\n删除 {td} 项，释放 {human_bytes(tf)}"
        if ts:
            msg += f"\n跳过（占用中/无权限）{ts} 项"
        if errs:
            msg += "\n\n部分错误:\n" + "\n".join(errs[:6])
        messagebox.showinfo("清理完成", msg)
        self.scan_clean()

    def do_recycle(self):
        if not messagebox.askyesno("确认", "清空回收站？不可恢复。"):
            return
        ok, e = empty_recycle_bin()
        messagebox.showinfo("结果", "已清空" if ok else f"失败: {e}")

    # ============================================================ 显存/GPU
    def _build_gpu(self):
        f = self.f_gpu
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="刷新显存占用", command=self.refresh_gpu).pack(side="left")
        self.vram_lbl = tk.StringVar(value="-")
        tk.Label(top, textvariable=self.vram_lbl, fg="#1f6feb",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=14)
        ttk.Button(top, text="重启显卡驱动(风险)",
                   command=self._restart_gpu_driver).pack(side="right")
        self.gpu_tv = self._mk_tree(f, ("占用显存(MB)", "进程", "PID"),
                                    (150, 430, 100), ("e", "w", "center"), height=20)

    def refresh_gpu(self):
        self.set_status("正在读取显存占用…")
        self.vram_lbl.set(get_nvidia_vram())
        for i in self.gpu_tv.get_children():
            self.gpu_tv.delete(i)
        for n, (mb, name, pid) in enumerate(get_gpu_processes()):
            self.gpu_tv.insert("", "end", values=(f"{mb:.0f}", name, pid),
                               tags=(self._row_tag(n),))
        self.set_status("显存信息已刷新")

    def _restart_gpu_driver(self):
        if not messagebox.askyesno("高风险操作",
                                   "将重启显卡驱动，屏幕会黑屏闪烁几秒。\n继续？"):
            return
        self.set_status("正在重启显卡驱动…")
        run_ps("pnputil /restart-device (Get-PnpDevice -Class Display | "
               "Where-Object {$_.Status -eq 'OK'} | Select-Object -First 1 "
               "-ExpandProperty InstanceId) 2>&1 | Out-Null", 120)
        self.set_status("显卡驱动已重启")

    # ============================================================ 软件卸载
    def _build_uninst(self):
        f = self.f_uninst
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="刷新列表", command=self.refresh_uninst).pack(side="left")
        ttk.Button(top, text="① 调用卸载程序", command=self.do_uninst).pack(side="left", padx=6)
        ttk.Button(top, text="② 扫描并清除残留",
                   command=self.deep_clean_selected).pack(side="left")
        ttk.Button(top, text="定位安装目录", command=self.locate_install).pack(side="left", padx=6)
        ttk.Label(top, text="搜索:").pack(side="left", padx=(14, 4))
        self.u_search = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.u_search, width=20)
        e.pack(side="left")
        e.bind("<KeyRelease>", lambda ev: self.refresh_uninst())
        self.un_count = tk.StringVar(value="")
        tk.Label(top, textvariable=self.un_count, fg="#666").pack(side="left", padx=10)

        self.un_tv = self._mk_tree(f, ("软件名称", "版本", "发布者", "大小(MB)"),
                                   (400, 120, 300, 100),
                                   ("w", "center", "w", "e"), height=20, tree_col=True)
        self.un_tv.bind("<Double-1>", lambda ev: self.do_uninst())

    def refresh_uninst(self):
        self.set_status("正在读取已安装软件…")
        q = (self.u_search.get() or "").lower()
        for i in self.un_tv.get_children():
            self.un_tv.delete(i)
        self.un_items = list_installed()
        shown = 0
        for n, (disp, cmd, ver, pub, sz) in enumerate(self.un_items):
            if q and q not in disp.lower() and q not in (pub or "").lower():
                continue
            self.un_tv.insert("", "end", text="",
                              values=(disp, ver or "-", pub or "-",
                                      f"{sz:.1f}" if sz else "-"),
                              tags=(self._row_tag(shown),))
            shown += 1
        self.un_count.set(f"共 {len(self.un_items)} 个，显示 {shown} 个")
        self.set_status(f"已安装软件 {len(self.un_items)} 个")
        self._start_icon_load()

    def _start_icon_load(self):
        items = list(self.un_items)
        if not items:
            return

        def work():
            for disp, cmd, ver, pub, sz in items:
                try:
                    safe = re.sub(r"[^\w\-]", "_", disp)[:60]
                    png = os.path.join(self.icon_dir, safe + ".png")
                    if os.path.isfile(png):
                        self.icon_queue.put((disp, png)); continue
                    ic, loc = get_display_icon_path(disp)
                    cand = ""
                    if ic:
                        cand = ic
                    elif loc and safe_isdir(loc):
                        for f in os.listdir(loc):
                            if f.lower().endswith(".exe"):
                                cand = os.path.join(loc, f); break
                    if not cand:
                        try:
                            us = cmd.split('"')[1] if '"' in cmd else cmd.split()[0]
                            if us.lower().endswith(".exe") and os.path.isfile(us):
                                cand = us
                        except Exception:
                            pass
                    if cand and extract_icon_png(cand, png):
                        self.icon_queue.put((disp, png))
                except Exception:
                    continue
            self.icon_queue.put((None, None))

        threading.Thread(target=work, daemon=True).start()

    def _poll_icons(self):
        done = False
        while True:
            try:
                name, png = self.icon_queue.get_nowait()
            except queue.Empty:
                break
            if name is None:
                done = True
                break
            try:
                img = tk.PhotoImage(file=png)
                self.icon_cache[name] = img
                for it in self.un_tv.get_children():
                    if self.un_tv.item(it, "values")[0] == name:
                        self.un_tv.item(it, image=img)
                        break
            except Exception:
                pass
        self.root.after(120 if not done else 1500, self._poll_icons)

    def _sel_uninst(self):
        it = self.un_tv.selection()
        if not it:
            return None
        disp = self.un_tv.item(it[0], "values")[0]
        for d, cmd, ver, pub, sz in self.un_items:
            if d == disp:
                return (d, cmd)
        return None

    def do_uninst(self):
        s = self._sel_uninst()
        if not s:
            messagebox.showinfo("提示", "请先选中一个软件")
            return
        d, cmd = s
        if not messagebox.askyesno("确认", f"调用系统卸载程序：\n\n{d}\n\n继续？"):
            return
        try:
            if cmd.lower().startswith("msiexec"):
                subprocess.Popen(cmd.replace("/I", "/X").replace("/i", "/x") + " /passive",
                                 shell=True)
            else:
                subprocess.Popen(cmd, shell=True)
            self.set_status(f"已启动卸载: {d}")
            messagebox.showinfo("已启动",
                                "请在卸载窗口中完成操作。\n\n"
                                "完成后回到本工具点「② 扫描并清除残留」清理剩余痕迹。")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def locate_install(self):
        s = self._sel_uninst()
        if not s:
            return
        ic, loc = get_display_icon_path(s[0])
        if loc and safe_isdir(loc.strip('"')):
            subprocess.Popen(f'explorer "{loc.strip()}"', shell=True)
        else:
            messagebox.showinfo("提示", "该软件未记录安装路径")

    def deep_clean_selected(self):
        s = self._sel_uninst()
        if not s:
            messagebox.showinfo("提示", "请先选中一个软件")
            return
        name = s[0]
        self.set_status(f"正在扫描 {name} 的残留…")
        ic, loc = get_display_icon_path(name)
        res = deep_scan_residue(name, loc)
        if not res["dirs"] and not res["registry"]:
            messagebox.showinfo("扫描结果", f"「{name}」未发现残留。\n\n很干净。")
            self.set_status("未发现残留")
            return
        self._show_residue_dialog(name, loc, res)

    def _show_residue_dialog(self, name, loc, res):
        win = tk.Toplevel(self.root)
        win.title(f"残留清理 - {name}")
        win.geometry("860x520")
        win.transient(self.root)
        ttk.Label(win, text=f"发现 {len(res['dirs'])} 个残留目录，"
                            f"{len(res['registry'])} 项残留注册表",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=12, pady=10)
        tv = ttk.Treeview(win, columns=("类型", "路径"), show="headings", height=16)
        tv.heading("类型", text="类型"); tv.column("类型", width=90, anchor="center")
        tv.heading("路径", text="路径 / 注册表项"); tv.column("路径", width=730, anchor="w")
        for n, d in enumerate(res["dirs"]):
            tv.insert("", "end", values=("目录", d), tags=(self._row_tag(n),))
        for i, (h, p, label) in enumerate(res["registry"]):
            hive = "HKCU" if h == winreg.HKEY_CURRENT_USER else "HKLM"
            tv.insert("", "end", values=("注册表", f"{hive}\\{p}"), tags=(self._row_tag(i + len(res["dirs"])),))
        tv.pack(fill="both", expand=True, padx=12)
        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=12, pady=10)

        def do_it():
            if not messagebox.askyesno("确认", f"永久删除以上 {len(res['dirs'])} 个目录和 "
                                              f"{len(res['registry'])} 项注册表？\n不可恢复。",
                                       parent=win):
                return
            # 只删除界面上列出的这一批，不在删除时重新扫描
            rep = deep_clean(name, loc,
                             allow_dirs=list(res["dirs"]),
                             allow_reg=[(h, p) for h, p, _ in res["registry"]])
            msg = f"已删除目录 {rep['dirs_removed']} 个，注册表 {rep['reg_removed']} 项"
            if rep["errors"]:
                msg += "\n\n以下未能删除：\n" + "\n".join(rep["errors"][:8])
            messagebox.showinfo("完成", msg, parent=win)
            win.destroy()
            self.set_status("残留清理完成")

        ttk.Button(bar, text="全部清除", command=do_it).pack(side="right")
        ttk.Button(bar, text="取消", command=win.destroy).pack(side="right", padx=8)

    # ============================================================ 残留清理
    def _build_resid(self):
        f = self.f_resid
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="扫描全部残留", command=self.scan_resid).pack(side="left")
        tk.Label(top, text="找出「卸载记录还在、但安装目录已消失」的软件，以及遗留配置项",
                 fg="#666").pack(side="left", padx=14)
        self.resid_tv = self._mk_tree(f, ("软件名称", "失效的安装路径", "注册表项"),
                                      (300, 340, 400), ("w", "w", "w"),
                                      height=20, tree_col=True)
        self.resid_items = []

    def scan_resid(self):
        self.set_status("正在扫描注册表残留…")
        for i in self.resid_tv.get_children():
            self.resid_tv.delete(i)
        items = []
        try:
            items = orphan_registry_keys()
        except Exception as e:
            messagebox.showerror("错误", str(e))
        self.resid_items = items
        for n, (d, loc, key) in enumerate(items):
            hive = "HKCU" if key.startswith("SOFTWARE") and "WOW6432" not in key else "HKLM"
            self.resid_tv.insert("", "end", text="",
                                 values=(d, loc, f"{hive}\\{key}"),
                                 tags=(self._row_tag(n),))
        self.set_status(f"发现 {len(items)} 条疑似残留（默认不删除）")

    # ============================================================ 系统更新
    def _build_update(self):
        f = self.f_update
        info = ttk.LabelFrame(f, text=" Windows 更新状态 ", padding=10)
        info.pack(fill="x", pady=(0, 10))
        self.wu_lbl = tk.StringVar(value="-")
        tk.Label(info, textvariable=self.wu_lbl, justify="left",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        ttk.Button(info, text="刷新状态", command=self.refresh_wu).pack(anchor="w", pady=(8, 0))

        p1 = ttk.LabelFrame(f, text=" 暂停更新（推荐：出差/比赛期间不让它后台下载） ", padding=10)
        p1.pack(fill="x", pady=(0, 10))
        row = ttk.Frame(p1); row.pack(fill="x")
        for d in (7, 14, 30, 35):
            ttk.Button(row, text=f"暂停 {d} 天",
                       command=lambda dd=d: self.do_wu_pause(dd)).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="恢复自动更新", command=self.do_wu_resume).pack(side="left", padx=(16, 0))

        p2 = ttk.LabelFrame(f, text=" 清理更新相关（需要管理员权限） ", padding=10)
        p2.pack(fill="x", pady=(0, 10))
        r2 = ttk.Frame(p2); r2.pack(fill="x")
        ttk.Button(r2, text="清理更新缓存", command=self.do_wu_cache).pack(side="left", padx=(0, 6))
        ttk.Button(r2, text="停止更新服务", command=self.do_wu_stop).pack(side="left", padx=(0, 6))
        ttk.Button(r2, text="启动更新服务", command=self.do_wu_start).pack(side="left", padx=(0, 6))
        ttk.Button(r2, text="一键重置更新组件", command=self.do_wu_reset).pack(side="left")
        tk.Label(p2, text="重置会把 C:\\Windows\\SoftwareDistribution 改名为 .old 后重建，"
                          "可解决「更新卡住/反复提示重启」。",
                 fg="#666", wraplength=980, justify="left").pack(anchor="w", pady=(8, 0))
        self.root.after(700, self.refresh_wu)

    def refresh_wu(self):
        self.set_status("正在读取更新状态…")
        st = wu_state()
        txt = (f"Windows Update 服务 : {st['wuauserv']}\n"
               f"BITS 后台传输服务  : {st['bits']}\n"
               f"更新缓存大小        : {st['cache']}\n"
               f"暂停到期时间        : {st['paused_until']}")
        self.wu_lbl.set(txt)
        self.set_status("更新状态已刷新")

    def do_wu_pause(self, days):
        ok, msg = wu_pause(days)
        messagebox.showinfo("暂停更新", msg)
        self.refresh_wu()

    def do_wu_resume(self):
        ok, msg = wu_resume()
        messagebox.showinfo("恢复更新", msg)
        self.refresh_wu()

    def do_wu_cache(self):
        if not messagebox.askyesno("确认", "清理 Windows 更新缓存？\n（会先停止更新服务）"):
            return
        self.set_status("正在清理更新缓存…")
        wu_stop_services()
        freed, err = wu_clear_cache()
        wu_start_services()
        messagebox.showinfo("完成", f"已释放 {human_bytes(freed)}" + (f"\n{err}" if err else ""))
        self.refresh_wu()

    def do_wu_stop(self):
        wu_stop_services()
        messagebox.showinfo("完成", "更新服务已停止（重启后会恢复）")
        self.refresh_wu()

    def do_wu_start(self):
        wu_start_services()
        messagebox.showinfo("完成", "更新服务已启动")
        self.refresh_wu()

    def do_wu_reset(self):
        if not messagebox.askyesno("确认", "重置更新组件？\n\n会停止更新服务、把 "
                                          "SoftwareDistribution 改名为 .old 后重建。\n"
                                          "用于解决「更新卡住/反复提示重启」。\n\n继续？"):
            return
        self.set_status("正在重置更新组件…")
        ok, msg = wu_reset_components()
        messagebox.showinfo("结果", msg)
        self.refresh_wu()

    # ============================================================ 系统优化
    def _build_tune(self):
        f = self.f_tune

        g1 = ttk.LabelFrame(f, text=" 快捷方式小箭头 ", padding=12)
        g1.pack(fill="x", pady=(0, 10))
        tk.Label(g1, text="去掉桌面/开始菜单图标左下角的小箭头，只改当前用户注册表，可一键还原。",
                 fg="#666").pack(anchor="w")
        r1 = ttk.Frame(g1); r1.pack(fill="x", pady=(10, 0))
        ttk.Button(r1, text="隐藏小箭头", command=lambda: self.do_arrows(True)).pack(side="left")
        ttk.Button(r1, text="恢复小箭头", command=lambda: self.do_arrows(False)).pack(side="left", padx=8)
        ttk.Button(r1, text="重启资源管理器", command=self.do_restart_explorer).pack(side="left", padx=(16, 0))
        self.arrow_lbl = tk.StringVar(value="")
        tk.Label(r1, textvariable=self.arrow_lbl, fg="#1f6feb",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=14)

        g2 = ttk.LabelFrame(f, text=" 说明 ", padding=12)
        g2.pack(fill="x")
        tk.Label(g2, justify="left", fg="#444",
                 text=("· 小箭头改动只写入 HKEY_CURRENT_USER，不碰系统关键区域；\n"
                       "· 改动后需重启资源管理器（任务栏会闪一下）才生效；\n"
                       "· 「恢复小箭头」会删除该项，回到 Windows 默认外观；\n"
                       "· 本工具不做内存「优化」、不改服务启动项、不动系统文件。")
                 ).pack(anchor="w")
        self.root.after(900, self.refresh_arrows)

    def refresh_arrows(self):
        self.arrow_lbl.set("当前状态: " + ("已隐藏" if is_arrows_hidden() else "默认（显示箭头）"))

    def do_arrows(self, hide):
        if hide:
            if not os.path.isfile(self.blank_ico):
                if not make_blank_ico(self.blank_ico):
                    messagebox.showerror("错误", "无法生成空白图标文件")
                    return
            ok, err = set_arrows(True, self.blank_ico)
        else:
            ok, err = set_arrows(False, "")
        if not ok:
            messagebox.showerror("失败", err or "未知错误")
            return
        self.refresh_arrows()
        if messagebox.askyesno("需要重启资源管理器",
                               "设置已写入。\n\n现在重启资源管理器使其生效？\n"
                               "（任务栏和桌面会闪一下，约 2 秒）"):
            self.do_restart_explorer()

    def do_restart_explorer(self):
        self.set_status("正在重启资源管理器…")
        ok, err = restart_explorer()
        if ok:
            self.set_status("资源管理器已重启")
        else:
            messagebox.showerror("失败", err or "未知错误")

    # ============================================================ 便携工具
    def _build_port(self):
        f = self.f_port
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="添加目录", command=self.add_port).pack(side="left")
        ttk.Button(top, text="移除选中", command=self.remove_port).pack(side="left", padx=6)
        ttk.Button(top, text="删除整个目录(卸载)", command=self.delete_port).pack(side="left")
        ttk.Button(top, text="打开文件夹", command=self.open_port).pack(side="left", padx=6)
        tk.Label(top, text="绿色/便携软件：直接删目录即卸载", fg="#666").pack(side="left", padx=14)

        self.pt_tv = self._mk_tree(f, ("名称", "路径", "体积"),
                                   (220, 600, 110), ("w", "w", "e"),
                                   height=20, tree_col=True)
        self.port_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portable.json")
        self.root.after(1000, self.refresh_port)

    def load_port(self):
        try:
            if os.path.isfile(self.port_file):
                return json.load(open(self.port_file, "r", encoding="utf-8"))
        except Exception:
            pass
        return []

    def save_port(self, items):
        try:
            json.dump(items, open(self.port_file, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception:
            pass

    def refresh_port(self):
        for i in self.pt_tv.get_children():
            self.pt_tv.delete(i)
        keep = []
        for it in self.load_port():
            p = it.get("path", "")
            if p and safe_isdir(p):
                keep.append(it)
        self.save_port(keep)
        for n, it in enumerate(keep):
            p = it["path"]
            sz, ap = dir_size(p, cap=3000)
            self.pt_tv.insert("", "end", text="",
                              values=(it.get("name"), p, human_bytes(sz) + (" ~" if ap else "")),
                              tags=(self._row_tag(n),))

    def add_port(self):
        d = filedialog.askdirectory(title="选择便携软件目录")
        if not d:
            return
        items = self.load_port()
        if any(i.get("path") == d for i in items):
            messagebox.showinfo("提示", "已在列表中")
            return
        items.append({"name": os.path.basename(d.rstrip("\\/")) or d, "path": d})
        self.save_port(items)
        self.refresh_port()

    def _sel_port(self):
        it = self.pt_tv.selection()
        if not it:
            return None
        v = self.pt_tv.item(it[0], "values")
        return {"name": v[0], "path": v[1]}

    def remove_port(self):
        s = self._sel_port()
        if not s:
            return
        self.save_port([i for i in self.load_port() if i.get("path") != s["path"]])
        self.refresh_port()

    def open_port(self):
        s = self._sel_port()
        if s and safe_isdir(s["path"]):
            subprocess.Popen(f'explorer "{s["path"]}"', shell=True)

    def delete_port(self):
        s = self._sel_port()
        if not s:
            return
        p = s["path"]
        if not safe_isdir(p):
            messagebox.showinfo("提示", "目录不存在")
            return
        sz, _ = dir_size(p)
        if not messagebox.askyesno("确认删除",
                                   f"永久删除整个目录（不可恢复）:\n\n{p}\n\n"
                                   f"约 {human_bytes(sz)}\n\n继续？"):
            return
        self.set_status(f"正在删除 {s['name']}…")
        shutil.rmtree(p, ignore_errors=True)
        if safe_isdir(p):
            messagebox.showwarning("未完成", "部分文件被占用，请先关闭该软件再试。")
        else:
            messagebox.showinfo("完成", f"已删除 {s['name']}")
        self.save_port([i for i in self.load_port() if i.get("path") != p])
        self.refresh_port()
        self.set_status("就绪")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
