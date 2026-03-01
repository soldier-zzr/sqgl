# -*- coding: utf-8 -*-
"""AI超级分身 音频下载工具 - 启动入口。"""

import sys
import os
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog, messagebox
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui.app import AudioDownloaderApp

# 优先从 config.py 读取访问密码，若不存在则使用默认占位符
try:
    from config import ACCESS_CODE  # type: ignore
except ImportError:
    ACCESS_CODE = "change_me"


def _normalize_code(text: str) -> str:
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    return s.strip().lower()


def _hide_console_window() -> None:
    if os.name != "nt":
        return
    if os.environ.get("VOICE_SHOW_CONSOLE") == "1":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _check_access() -> bool:
    root = tk.Tk()
    root.withdraw()
    try:
        expected = _normalize_code(ACCESS_CODE)
        for _ in range(3):
            code = simpledialog.askstring("访问验证", "请输入访问密码：", show="*", parent=root)
            if code is None:
                return False
            if _normalize_code(code) == expected:
                return True
            messagebox.showerror("访问验证", "密码错误，请重试。", parent=root)
        messagebox.showerror("访问验证", "密码连续错误 3 次，程序将退出。", parent=root)
        return False
    finally:
        root.destroy()


if __name__ == "__main__":
    try:
        _hide_console_window()
        if not _check_access():
            sys.exit(0)
        app = AudioDownloaderApp()
        app.run()
    except Exception as exc:
        # 在隐藏控制台模式下给出明确错误提示，避免“输入后直接消失”的体验
        err_root = tk.Tk()
        err_root.withdraw()
        messagebox.showerror("程序错误", f"程序启动失败：{exc}", parent=err_root)
        err_root.destroy()
        raise
