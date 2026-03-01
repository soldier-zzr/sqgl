# -*- coding: utf-8 -*-
"""UI theme tokens for the customtkinter app."""

import customtkinter as ctk


THEME = {
    "bg": "#F3F6FB",
    "card": "#FFFFFF",
    "panel": "#F8FAFC",
    "border": "#DCE3EE",
    "input_border": "#CFD8E6",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "secondary": "#E2E8F0",
    "secondary_hover": "#CBD5E1",
    "text": "#0F172A",
    "muted": "#64748B",
    "placeholder": "#94A3B8",
    "success": "#059669",
    "warning": "#D97706",
    "danger": "#DC2626",
}

STATE_DOT = {
    "idle": "#94A3B8",
    "connecting": "#D97706",
    "ready": "#059669",
    "processing": "#2563EB",
    "closing": "#D97706",
    "closed": "#94A3B8",
}

STATE_TEXT = {
    "idle": "未启动",
    "connecting": "连接中",
    "ready": "已就绪",
    "processing": "处理中",
    "closing": "关闭中",
    "closed": "已关闭",
}


def apply_theme() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

