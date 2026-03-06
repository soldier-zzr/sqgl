# -*- coding: utf-8 -*-
"""Filename sanitizing and deterministic renaming."""

from __future__ import annotations

import re
from pathlib import Path


_INVALID_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def sanitize_prefix(text: str, max_len: int = 18) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = _INVALID_RE.sub("", cleaned).replace(" ", "")
    cleaned = cleaned.strip("._")
    if not cleaned:
        cleaned = "output"
    return cleaned[:max_len]


def build_filename(text: str, ext: str, *, index: int | None = None) -> str:
    normalized_ext = ext if ext.startswith(".") else f".{ext}"
    # 支持「备注::文案」格式："::" 前面作为文件名，否则取前两个字
    if "::" in text:
        raw_prefix = text.split("::", 1)[0]
        prefix = sanitize_prefix(raw_prefix, max_len=60)
    else:
        prefix = sanitize_prefix(text, max_len=2)
    if index is None:
        return f"{prefix}{normalized_ext.lower()}"
    return f"{index:03d}_{prefix}{normalized_ext.lower()}"


def rename_output_file(
    original_path: str | Path,
    *,
    index: int | None = None,
    text: str,
) -> tuple[Path, str | None]:
    source = Path(original_path)
    if not source.exists():
        return source, f"文件不存在：{source.name}"

    target = source.with_name(build_filename(text=text, ext=source.suffix or ".mp3", index=index))
    if target == source:
        return source, None

    try:
        # 按用户需求：不要 (1) 后缀，遇到同名直接覆盖旧文件
        if target.exists():
            target.unlink()
        source.rename(target)
        return target, None
    except Exception as exc:
        return source, f"重命名失败：{exc}"
