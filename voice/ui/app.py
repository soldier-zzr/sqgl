# -*- coding: utf-8 -*-
"""CustomTkinter main UI with full queue flow."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

import customtkinter as ctk

from browser import BrowserSession, OUTPUT_DIR
from utils.naming import rename_output_file

from .models import QueueItem, QueueStatus
from .queue_manager import QueueManager
from .theme import STATE_DOT, STATE_TEXT, THEME, apply_theme

BASE_URL = "https://ip.fenshen123.com/#/create"
PLACEHOLDER_TEXT = "请在此粘贴需要处理的文案内容（每行一条）..."

STATUS_LABEL = {
    QueueStatus.PENDING: "待处理",
    QueueStatus.RUNNING: "处理中",
    QueueStatus.SUCCESS: "成功",
    QueueStatus.FAILED: "失败",
    QueueStatus.SKIPPED: "已跳过",
}


class AudioDownloaderApp(ctk.CTk):
    def __init__(self) -> None:
        apply_theme()
        super().__init__()

        self.title("AI超级分身 音频下载工具")
        self.geometry("1080x680")
        self.minsize(960, 620)
        self.configure(fg_color=THEME["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_icon()

        self._session: BrowserSession | None = None
        self._session_ready = False
        self._processing = False
        self._closing = False
        self._current_item_id: str | None = None
        self._last_task_error: str | None = None
        self._placeholder_active = True
        self._conn_state = "idle"

        self.queue = QueueManager()

        self._setup_tree_style()
        self._build_ui()
        self._bind_shortcuts()
        self._set_connection_state("idle")
        self._set_status_message("就绪，请先开启浏览器，再开始队列处理")
        self._refresh_progress()
        self._update_controls()

    def _setup_icon(self) -> None:
        try:
            base = (
                Path(getattr(sys, "_MEIPASS", ""))
                if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parent.parent
            )
            for name in ("logo.png", "logo.ico"):
                icon_path = base / name
                if not icon_path.exists():
                    continue
                if name.endswith(".png"):
                    icon = tk.PhotoImage(file=str(icon_path))
                    self.iconphoto(True, icon)
                    self._icon = icon
                else:
                    self.iconbitmap(str(icon_path))
                break
        except Exception:
            pass

    def _setup_tree_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Queue.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=THEME["text"],
            borderwidth=0,
            rowheight=30,
            relief="flat",
            font=("Microsoft YaHei", 10),
        )
        style.configure(
            "Queue.Treeview.Heading",
            background="#E2E8F0",
            foreground="#334155",
            relief="flat",
            font=("Microsoft YaHei", 10, "bold"),
        )
        style.map(
            "Queue.Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", "#1D4ED8")],
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=THEME["card"], corner_radius=12, border_width=1, border_color=THEME["border"])
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            top,
            text="AI超级分身 音频下载工具",
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 22, "bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 4))

        self.conn_state_lbl = ctk.CTkLabel(
            top,
            text="● 未启动",
            text_color=STATE_DOT["idle"],
            font=ctk.CTkFont("Microsoft YaHei", 13, "bold"),
        )
        self.conn_state_lbl.grid(row=0, column=1, sticky="e", padx=16, pady=(14, 4))

        self.status_lbl = ctk.CTkLabel(
            top,
            text="",
            anchor="w",
            justify="left",
            text_color=THEME["muted"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        )
        self.status_lbl.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=7)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=THEME["card"], corner_radius=12, border_width=1, border_color=THEME["border"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left,
            text="输入文案（按行拆分）",
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 14, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        self.input_box = ctk.CTkTextbox(
            left,
            fg_color="#FFFFFF",
            border_width=1,
            border_color=THEME["input_border"],
            text_color=THEME["placeholder"],
            corner_radius=10,
            wrap="word",
            font=ctk.CTkFont("Microsoft YaHei", 12),
        )
        self.input_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.input_box.insert("1.0", PLACEHOLDER_TEXT)

        txt = self.input_box._textbox
        txt.bind("<FocusIn>", self._on_input_focus_in, add="+")
        txt.bind("<FocusOut>", self._on_input_focus_out, add="+")

        left_actions = ctk.CTkFrame(left, fg_color="transparent")
        left_actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        left_actions.grid_columnconfigure((0, 1, 2), weight=1)
        left_actions.grid_rowconfigure(1, weight=0)

        self.add_btn = ctk.CTkButton(
            left_actions,
            text="加入队列",
            command=self._on_add_queue,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            font=ctk.CTkFont("Microsoft YaHei", 12, "bold"),
        )
        self.add_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            left_actions,
            text="清空输入",
            command=self._clear_input_box,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            left_actions,
            text="从剪贴板粘贴",
            command=self._paste_from_clipboard,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        ctk.CTkButton(
            left_actions,
            text="导入 Excel 自动生成话术",
            command=self._on_import_excel,
            fg_color=THEME.get("accent", "#1a7f64"),
            hover_color=THEME.get("accent_hover", "#145f4c"),
            font=ctk.CTkFont("Microsoft YaHei", 12),
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        right = ctk.CTkFrame(body, fg_color=THEME["card"], corner_radius=12, border_width=1, border_color=THEME["border"])
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            right,
            text="任务队列",
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 14, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        queue_actions = ctk.CTkFrame(right, fg_color="transparent")
        queue_actions.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        queue_actions.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.start_queue_btn = ctk.CTkButton(
            queue_actions,
            text="开始队列",
            command=self._on_start_queue,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            font=ctk.CTkFont("Microsoft YaHei", 12, "bold"),
        )
        self.start_queue_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.stop_queue_btn = ctk.CTkButton(
            queue_actions,
            text="停止当前",
            command=self._on_stop_current,
            fg_color="#F59E0B",
            hover_color="#D97706",
            font=ctk.CTkFont("Microsoft YaHei", 12, "bold"),
        )
        self.stop_queue_btn.grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            queue_actions,
            text="移除选中",
            command=self._on_remove_selected,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        ).grid(row=0, column=2, sticky="ew", padx=6)

        ctk.CTkButton(
            queue_actions,
            text="清空已完成",
            command=self._on_clear_completed,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        tree_frame = ctk.CTkFrame(right, fg_color=THEME["panel"], corner_radius=10, border_width=1, border_color=THEME["input_border"])
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        self.queue_tree = ttk.Treeview(
            tree_frame,
            columns=("idx", "text", "status", "result"),
            show="headings",
            style="Queue.Treeview",
            selectmode="extended",
        )
        self.queue_tree.heading("idx", text="序号")
        self.queue_tree.heading("text", text="文案")
        self.queue_tree.heading("status", text="状态")
        self.queue_tree.heading("result", text="输出/错误")
        self.queue_tree.column("idx", width=68, anchor="center", stretch=False)
        self.queue_tree.column("text", width=220, anchor="w")
        self.queue_tree.column("status", width=90, anchor="center", stretch=False)
        self.queue_tree.column("result", width=260, anchor="w")
        self.queue_tree.grid(row=0, column=0, sticky="nsew")

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.queue_tree.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        self.queue_tree.configure(yscrollcommand=scroll_y.set)

        self.queue_tree.tag_configure("pending", foreground=THEME["muted"])
        self.queue_tree.tag_configure("running", foreground=THEME["primary"], background="#EFF6FF")
        self.queue_tree.tag_configure("success", foreground="#065F46", background="#D1FAE5")
        self.queue_tree.tag_configure("failed",  foreground="#991B1B", background="#FEE2E2")
        self.queue_tree.tag_configure("skipped", foreground=THEME["warning"], background="#FEF9C3")

        progress_wrap = ctk.CTkFrame(right, fg_color="transparent")
        progress_wrap.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        progress_wrap.grid_columnconfigure(0, weight=1)

        self.progress_lbl = ctk.CTkLabel(
            progress_wrap,
            text="进度：0/0",
            anchor="w",
            text_color=THEME["muted"],
            font=ctk.CTkFont("Microsoft YaHei", 12),
        )
        self.progress_lbl.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.progress_bar = ctk.CTkProgressBar(progress_wrap, height=12, progress_color=THEME["primary"])
        self.progress_bar.grid(row=1, column=0, sticky="ew")
        self.progress_bar.set(0)

        bottom = ctk.CTkFrame(self, fg_color=THEME["card"], corner_radius=12, border_width=1, border_color=THEME["border"])
        bottom.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 14))
        bottom.grid_columnconfigure((0, 1, 2), weight=1)

        self.open_browser_btn = ctk.CTkButton(
            bottom,
            text="开启浏览器",
            command=self._on_open_browser,
            fg_color=THEME["primary"],
            hover_color=THEME["primary_hover"],
            font=ctk.CTkFont("Microsoft YaHei", 13, "bold"),
        )
        self.open_browser_btn.grid(row=0, column=0, sticky="ew", padx=(14, 8), pady=14)

        self.close_browser_btn = ctk.CTkButton(
            bottom,
            text="关闭浏览器",
            command=self._close_session,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 13),
        )
        self.close_browser_btn.grid(row=0, column=1, sticky="ew", padx=8, pady=14)

        ctk.CTkButton(
            bottom,
            text="打开输出目录",
            command=self._open_output_dir,
            fg_color=THEME["secondary"],
            hover_color=THEME["secondary_hover"],
            text_color=THEME["text"],
            font=ctk.CTkFont("Microsoft YaHei", 13),
        ).grid(row=0, column=2, sticky="ew", padx=(8, 14), pady=14)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-Return>", self._on_ctrl_enter)
        self.bind_all("<Control-Shift-Return>", self._on_ctrl_shift_enter)

    def _on_ctrl_enter(self, _event):
        self._on_add_queue()
        return "break"

    def _on_ctrl_shift_enter(self, _event):
        self._on_start_queue()
        return "break"

    def _on_input_focus_in(self, _event):
        if not self._placeholder_active:
            return
        self.input_box.delete("1.0", "end")
        self.input_box.configure(text_color=THEME["text"])
        self._placeholder_active = False

    def _on_input_focus_out(self, _event):
        content = self.input_box.get("1.0", "end").strip()
        if content and content != PLACEHOLDER_TEXT:
            self._placeholder_active = False
            self.input_box.configure(text_color=THEME["text"])
            return
        self._placeholder_active = True
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", PLACEHOLDER_TEXT)
        self.input_box.configure(text_color=THEME["placeholder"])

    def _set_connection_state(self, state: str) -> None:
        self._conn_state = state
        state_text = STATE_TEXT.get(state, state)
        dot_color = STATE_DOT.get(state, THEME["muted"])
        self.conn_state_lbl.configure(text=f"● {state_text}", text_color=dot_color)

    def _set_status_message(self, msg: str, *, color: str | None = None) -> None:
        self.status_lbl.configure(text=msg, text_color=color or THEME["muted"])

    def _effective_input(self) -> str:
        content = self.input_box.get("1.0", "end").strip()
        if not content or content == PLACEHOLDER_TEXT:
            return ""
        # 防止占位符状态偶发不同步导致“有文案却提示空”的问题
        if self._placeholder_active:
            self._placeholder_active = False
            self.input_box.configure(text_color=THEME["text"])
        return content

    def _clear_input_box(self) -> None:
        self.input_box.delete("1.0", "end")
        self._placeholder_active = True
        self.input_box.insert("1.0", PLACEHOLDER_TEXT)
        self.input_box.configure(text_color=THEME["placeholder"])

    def _paste_from_clipboard(self) -> None:
        try:
            content = self.clipboard_get().strip()
        except Exception:
            content = ""
        if not content:
            messagebox.showinfo("提示", "剪贴板为空")
            return
        if self._placeholder_active:
            self.input_box.delete("1.0", "end")
            self.input_box.configure(text_color=THEME["text"])
            self._placeholder_active = False
        self.input_box.insert("end", content)
        self._set_status_message("已从剪贴板粘贴文案")

    def _on_add_queue(self) -> None:
        raw = self._effective_input()
        if not raw:
            messagebox.showwarning("提示", "请输入文案内容（每行一条）")
            return

        created = self.queue.add_from_text(raw)
        if not created:
            messagebox.showwarning("提示", "未检测到有效文案行")
            return

        for item in created:
            self._upsert_tree_item(item)

        self._clear_input_box()
        self._refresh_progress()
        self._update_controls()
        self._set_status_message(f"已加入 {len(created)} 条任务")

    def _on_start_queue(self) -> None:
        if not self._session_ready or self._session is None:
            messagebox.showwarning("提示", "浏览器未就绪，请先点击「开启浏览器」")
            return
        if self._processing:
            return
        if not self.queue.has_pending():
            messagebox.showinfo("提示", "没有待处理任务")
            return

        self._processing = True
        self._dispatch_next_task()
        self._update_controls()

    def _dispatch_next_task(self) -> None:
        if not self._processing or self._session is None or not self._session_ready:
            return

        item = self.queue.get_next_pending()
        if item is None:
            self._processing = False
            self._current_item_id = None
            self._set_connection_state("ready")
            self._set_status_message("队列处理完成", color=THEME["success"])
            self._update_controls()
            return

        self._last_task_error = None
        self._current_item_id = item.id
        self.queue.mark(item.id, QueueStatus.RUNNING)
        self._upsert_tree_item(item)
        self._set_connection_state("processing")
        self._set_status_message(f"正在处理 {item.index:03d}：{self._preview_text(item.text, 30)}")
        self._refresh_progress()
        self._session.submit(item.text)

    def _on_stop_current(self) -> None:
        if self._session is None:
            return
        if self._current_item_id:
            item = self.queue.mark(self._current_item_id, QueueStatus.SKIPPED, error="用户中断")
            if item:
                self._upsert_tree_item(item)
        self._processing = False
        self._current_item_id = None
        self._refresh_progress()
        self._set_status_message("正在停止并关闭浏览器...")
        self._close_session()

    def _on_remove_selected(self) -> None:
        selected = set(self.queue_tree.selection())
        if not selected:
            return
        if self._current_item_id and self._current_item_id in selected:
            messagebox.showwarning("提示", "当前正在处理的任务不能移除")
            return
        removed = self.queue.remove(selected)
        for item_id in selected:
            if self.queue_tree.exists(item_id):
                self.queue_tree.delete(item_id)
        self._refresh_progress()
        self._update_controls()
        self._set_status_message(f"已移除 {removed} 条任务")

    def _on_clear_completed(self) -> None:
        removed_ids = self.queue.clear_completed()
        if not removed_ids:
            self._set_status_message("没有可清理的已完成任务")
            return
        for item_id in removed_ids:
            if self.queue_tree.exists(item_id):
                self.queue_tree.delete(item_id)
        self._refresh_progress()
        self._update_controls()
        self._set_status_message(f"已清空 {len(removed_ids)} 条已完成任务")

    def _on_open_browser(self) -> None:
        if self._session is not None:
            self._set_status_message("浏览器会话已存在")
            return

        self._session_ready = False
        self._set_connection_state("connecting")
        self._set_status_message("正在启动浏览器，首次可能需要 10-30 秒...")
        self._update_controls()
        self._session = BrowserSession(
            base_url=BASE_URL,
            on_status=self._on_browser_status,
            on_done=self._on_task_done,
            on_ready=self._on_session_ready,
            on_end=self._on_session_ended,
        )

    def _close_session(self) -> None:
        if self._session is None:
            return
        self._session_ready = False
        self._set_connection_state("closing")
        self._update_controls()
        try:
            self._session.stop()
        except Exception:
            pass

    def _on_browser_status(self, msg: str) -> None:
        self._schedule_ui(lambda: self._handle_browser_status(msg))

    def _handle_browser_status(self, msg: str) -> None:
        self._set_status_message(msg)
        if msg.startswith("任务错误：") or msg.startswith("错误：") or "未捕获到音频" in msg:
            self._last_task_error = msg

    def _on_session_ready(self) -> None:
        self._schedule_ui(self._handle_session_ready)

    def _handle_session_ready(self) -> None:
        self._session_ready = True
        self._set_connection_state("ready")
        self._set_status_message("浏览器已就绪，可开始队列处理", color=THEME["success"])
        self._update_controls()

    def _on_task_done(self, filepath: str | None) -> None:
        self._schedule_ui(lambda: self._handle_task_done(filepath))

    def _handle_task_done(self, filepath: str | None) -> None:
        if not self._current_item_id:
            return

        item = self.queue.get(self._current_item_id)
        if item is None:
            self._current_item_id = None
            return

        if filepath:
            renamed, err = rename_output_file(filepath, text=item.text)
            status_note = err
            updated = self.queue.mark(
                item.id,
                QueueStatus.SUCCESS,
                output_path=renamed,
                error=status_note,
            )
            if err:
                self._set_status_message(f"任务 {item.index:03d} 完成，{err}", color=THEME["warning"])
            else:
                self._set_status_message(f"任务 {item.index:03d} 完成：{Path(renamed).name}", color=THEME["success"])
        else:
            reason = self._last_task_error or "生成失败"
            updated = self.queue.mark(item.id, QueueStatus.FAILED, error=reason)
            self._set_status_message(f"任务 {item.index:03d} 失败：{reason}", color=THEME["danger"])

        if updated:
            self._upsert_tree_item(updated)

        self._current_item_id = None
        self._last_task_error = None
        self._refresh_progress()

        if self._processing and self._session_ready and self._session is not None:
            self._dispatch_next_task()
        else:
            self._update_controls()

    def _on_session_ended(self) -> None:
        self._schedule_ui(self._handle_session_ended)

    def _handle_session_ended(self) -> None:
        self._session = None
        self._session_ready = False

        if self._processing and self._current_item_id:
            item = self.queue.mark(self._current_item_id, QueueStatus.SKIPPED, error="浏览器关闭，中断任务")
            if item:
                self._upsert_tree_item(item)

        self._processing = False
        self._current_item_id = None
        self._set_connection_state("closed")
        if not self._closing:
            self._set_status_message("浏览器已关闭，可重新开启")
        self._refresh_progress()
        self._update_controls()

    def _open_output_dir(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(OUTPUT_DIR))

    def _refresh_progress(self) -> None:
        c = self.queue.counts()
        total, done = c["total"], c["done"]
        self.progress_bar.set((done / total) if total else 0)
        self.progress_lbl.configure(
            text=f"进度：{done}/{total}   成功 {c['success']}   失败 {c['failed']}   跳过 {c['skipped']}"
        )

    def _update_controls(self) -> None:
        has_session = self._session is not None
        self.open_browser_btn.configure(state="disabled" if has_session else "normal")
        self.close_browser_btn.configure(state="normal" if has_session else "disabled")

        can_start_queue = (
            has_session
            and self._session_ready
            and not self._processing
            and self.queue.has_pending()
        )
        self.start_queue_btn.configure(state="normal" if can_start_queue else "disabled")
        self.stop_queue_btn.configure(state="normal" if self._processing and has_session else "disabled")

    def _upsert_tree_item(self, item: QueueItem) -> None:
        values = (
            f"{item.index:03d}",
            self._preview_text(item.text, 30),
            STATUS_LABEL[item.status],
            self._result_text(item),
        )
        tag = item.status.value
        if self.queue_tree.exists(item.id):
            self.queue_tree.item(item.id, values=values, tags=(tag,))
        else:
            self.queue_tree.insert("", "end", iid=item.id, values=values, tags=(tag,))

    @staticmethod
    def _preview_text(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return f"{text[:max_len]}..."

    @staticmethod
    def _result_text(item: QueueItem) -> str:
        if item.output_path:
            return Path(item.output_path).name
        if item.error:
            return AudioDownloaderApp._preview_text(item.error, 42)
        return "-"

    def _schedule_ui(self, func) -> None:
        if self._closing:
            return
        try:
            self.after(0, lambda: (self.winfo_exists() and not self._closing) and func())
        except Exception:
            pass

    def _on_close(self) -> None:
        self._closing = True
        try:
            if self._session is not None:
                self._session.stop()
        except Exception:
            pass
        self.destroy()

    # ── Excel 导入自动生成话术 ────────────────────────────────

    def _on_import_excel(self) -> None:
        material_path = filedialog.askopenfilename(
            title="选择话术原料 Excel（含姓名+赛道+备注列）",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
        )
        if not material_path:
            return

        # 检测 Excel 是否已含备注列，有则无需选第二个文件
        try:
            import openpyxl as _ox
            _wb = _ox.load_workbook(material_path, data_only=True, read_only=True)
            _ws = _wb.active
            _headers = [str(c or "").strip().lower() for c in next(_ws.iter_rows(min_row=1, max_row=1, values_only=True))]
            _wb.close()
            _has_remark = any(h in {"备注", "remark", "备注名", "mp3名"} for h in _headers)
        except Exception:
            _has_remark = False

        contacts_path = None
        if not _has_remark:
            contacts_path = filedialog.askopenfilename(
                title="未检测到备注列 — 请选择好友数据 Excel（A列昵称  B列备注）",
                filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")],
            )
            if not contacts_path:
                return

        self._set_status_message("正在生成话术，请稍候…")
        threading.Thread(
            target=self._generate_from_excel,
            args=(material_path, contacts_path),
            daemon=True,
        ).start()

    def _generate_from_excel(self, material_path: str, contacts_path: str | None) -> None:
        try:
            _root = Path(__file__).resolve().parent.parent
            if str(_root) not in sys.path:
                sys.path.insert(0, str(_root))
            from gen_tts_agent import (
                load_contacts, load_material, generate_script,
                DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL, API_DELAY,
            )
            from openai import OpenAI
            import time

            contacts = load_contacts(Path(contacts_path)) if contacts_path else {}
            material = load_material(Path(material_path))
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

            lines: list[str] = []
            skipped: list[str] = []
            failed: list[str] = []
            total = len(material)

            for i, item in enumerate(material):
                name = item["name"]
                track = item["track"]
                # 优先用原料表自带备注列，没有再查好友数据表
                remark = item.get("remark") or ""
                if not remark and contacts:
                    remark = contacts.get(name) or next(
                        (v for k, v in contacts.items() if k.lower() == name.lower()), ""
                    )
                if not remark:
                    skipped.append(name)
                    continue
                try:
                    script = generate_script(client, name, track)
                    script = script.replace("\n", " ").replace("\r", "").strip()
                    lines.append(f"{remark}::{script}")
                    self._schedule_ui(
                        lambda n=name, idx=i: self._set_status_message(
                            f"生成中 {idx + 1}/{total}：{n}"
                        )
                    )
                    if API_DELAY > 0 and i < total - 1:
                        time.sleep(API_DELAY)
                except Exception as e:
                    failed.append(f"{name}: {e}")

            if lines:
                self._schedule_ui(lambda: self._finish_excel_import(lines, skipped, failed))
            else:
                self._schedule_ui(
                    lambda: messagebox.showwarning("提示", "未生成任何话术，请检查 Excel 内容")
                )
        except Exception as e:
            self._schedule_ui(lambda: messagebox.showerror("错误", f"生成失败：{e}"))

    def _finish_excel_import(self, lines: list[str], skipped: list[str], failed: list[str]) -> None:
        created = self.queue.add_from_text("\n".join(lines))
        for item in created:
            self._upsert_tree_item(item)
        self._refresh_progress()
        self._update_controls()
        msg = f"已加入 {len(created)} 条任务"
        if skipped:
            msg += f"，跳过 {len(skipped)} 人（好友表未找到）"
        if failed:
            msg += f"，失败 {len(failed)} 人"
        self._set_status_message(msg)

    def run(self) -> None:
        self.mainloop()
