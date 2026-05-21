#!/usr/bin/env python3
from __future__ import annotations
# -*- coding: utf-8 -*-
"""
测试脚本：验证 ADB WiFi 设备连接和 Redis 连接是否正常。
在 apps/backend 目录下运行：
    .venv\Scripts\python.exe test_wifi_device.py
"""

import sys
# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import shutil
import subprocess
import platform as _platform


def _resolve_adb_path() -> str | None:
    """Find adb executable in PATH or common Android SDK locations."""
    adb_exe = "adb.exe" if _platform.system() == "Windows" else "adb"
    found = shutil.which(adb_exe)
    if found:
        return found
    candidates = []
    if _platform.system() == "Windows":
        candidates = [
            r"D:\platform-tools\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Android\android-sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%USERPROFILE%\android-sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
            os.path.expandvars(r"%ANDROID_SDK_ROOT%\platform-tools\adb.exe"),
        ]
    else:
        candidates = [
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
            "/usr/lib/android-sdk/platform-tools/adb",
            "/opt/android-sdk/platform-tools/adb",
        ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def test_redis():
    print("=" * 60)
    print("[1/4] 测试 Redis 连接")
    print("=" * 60)
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, socket_connect_timeout=3)
        r.ping()
        print("[OK] Redis 连接成功 (localhost:6379)")
        return True
    except Exception as e:
        print(f"[FAIL] Redis 连接失败: {e}")
        print("   提示: 如果你在 WSL 里启动了 Redis，请确保 Windows 能访问到它。")
        print("   可以在 WSL 里执行 'ip addr | grep eth0' 获取 WSL IP，")
        print("   然后把 backend/app/core/config.py 里的 redis_url 改成 redis://<wsl-ip>:6379/0")
        return False


def test_adb_path():
    print()
    print("=" * 60)
    print("[2/4] 测试 ADB 路径查找")
    print("=" * 60)
    adb_path = _resolve_adb_path()
    if adb_path:
        print(f"[OK] 找到 ADB: {adb_path}")
        return adb_path
    else:
        print("[FAIL] 未找到 ADB")
        print("   请确保 adb 在 PATH 中，或安装在以下常见路径之一:")
        print("   - D:/platform-tools/adb.exe")
        print("   - %LOCALAPPDATA%/Android/Sdk/platform-tools/adb.exe")
        print("   - %ANDROID_HOME%/platform-tools/adb.exe")
        return None


def test_adb_devices(adb_path: str):
    print()
    print("=" * 60)
    print("[3/4] 测试 ADB 设备扫描")
    print("=" * 60)
    try:
        result = subprocess.run(
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        print(f"adb 返回码: {result.returncode}")
        if result.stdout:
            print("adb stdout:")
            print(result.stdout)
        if result.stderr:
            print("adb stderr:")
            print(result.stderr)

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]
            devices = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1] in ("device", "offline", "unauthorized"):
                    devices.append(parts[0])
            if devices:
                print(f"[OK] 扫描到 {len(devices)} 个设备: {devices}")
            else:
                print("[WARN] adb 执行成功，但没有发现设备")
            return True
        else:
            print("[FAIL] adb 执行失败")
            return False
    except Exception as e:
        print(f"[FAIL] adb 扫描异常: {e}")
        return False


def test_adb_connect(adb_path: str):
    print()
    print("=" * 60)
    print("[4/4] 测试 ADB WiFi 连接")
    print("=" * 60)

    host = input("请输入设备 IP (如 192.168.2.58): ").strip()
    if not host:
        print("跳过连接测试")
        return

    pair_port = input("请输入配对端口 (pair port)，不需要配对直接回车: ").strip()
    if pair_port:
        pairing_code = input("请输入配对码: ").strip()
        pair_address = f"{host}:{pair_port}"
        print(f"执行: adb pair {pair_address}")
        try:
            result = subprocess.run(
                [adb_path, "pair", pair_address],
                input=pairing_code + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            print(f"pair stdout: {result.stdout.strip()}")
            print(f"pair stderr: {result.stderr.strip()}")
            if result.returncode != 0:
                print("[FAIL] 配对失败")
                return
            print("[OK] 配对成功")
        except Exception as e:
            print(f"[FAIL] 配对异常: {e}")
            return

    connect_port = input("请输入连接端口 (connect port，默认 5555): ").strip() or "5555"
    connect_address = f"{host}:{connect_port}"
    print(f"执行: adb connect {connect_address}")
    try:
        result = subprocess.run(
            [adb_path, "connect", connect_address],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        print(f"connect stdout: {result.stdout.strip()}")
        print(f"connect stderr: {result.stderr.strip()}")
        if result.returncode == 0 and ("connected to" in result.stdout or "already connected" in result.stdout):
            print("[OK] 连接成功")
        else:
            print("[FAIL] 连接失败")
    except Exception as e:
        print(f"[FAIL] 连接异常: {e}")


def main():
    print("NanoTest WiFi 设备调试脚本")
    print("=" * 60)

    redis_ok = test_redis()
    adb_path = test_adb_path()

    if not adb_path:
        print("\n[FAIL] ADB 未找到，后续测试跳过")
        sys.exit(1)

    test_adb_devices(adb_path)

    # 询问是否测试连接
    print()
    ans = input("是否测试 WiFi 连接? (y/N): ").strip().lower()
    if ans == "y":
        test_adb_connect(adb_path)

    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

    if not redis_ok:
        print("\n[WARN] 提醒: Redis 未连接，NanoTest 后端运行时可能会报错。")
        print("   请确保 Redis 已启动，且后端配置中的 redis_url 正确。")


if __name__ == "__main__":
    main()
