# -*- coding: utf-8 -*-
"""
AI超级分身 TTS 音频拦截下载器
支持持久化浏览器会话：登录一次，多次提交文案，无需重启
"""
import json
import queue
import sys
import threading
import base64
import time
from pathlib import Path
from typing import Optional, Callable, Tuple

from playwright.sync_api import sync_playwright, BrowserContext, Page


# 打包成 exe 后 __file__ 指向临时解压目录，用 sys.executable 确保
# cookies.json / output/ 始终保存在 exe 旁边
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    import os as _os
    # 优先使用 exe 旁边打包的浏览器，没有则回退到系统安装
    _local_bp = str(BASE_DIR / "ms-playwright")
    _system_bp = _os.path.join(_os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    if _os.path.isdir(_local_bp):
        _os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _local_bp
    elif _os.path.isdir(_system_bp):
        _os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _system_bp)
else:
    BASE_DIR = Path(__file__).resolve().parent
COOKIES_FILE = BASE_DIR / "cookies.json"
OUTPUT_DIR = BASE_DIR / "output"
LOGIN_URL = "https://ip.fenshen123.com/#/login"
USERNAME = "13920153343"
PASSWORD = "zhufeng123"

# 从同目录下 账号.txt 读取账号密码（优先级高于内置默认值）
_account_file = BASE_DIR / "账号.txt"
if _account_file.exists():
    for _line in _account_file.read_text(encoding="utf-8-sig").splitlines():
        _line = _line.strip()
        if _line.startswith("账号="):
            USERNAME = _line.split("=", 1)[1].strip()
        elif _line.startswith("密码="):
            PASSWORD = _line.split("=", 1)[1].strip()


# ── Cookie 管理 ────────────────────────────────────────────

def _load_cookies(context: BrowserContext) -> bool:
    if not COOKIES_FILE.exists():
        return False
    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        return True
    except Exception:
        return False


def _save_cookies(context: BrowserContext):
    try:
        cookies = context.cookies()
        COOKIES_FILE.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _is_logged_in(page: Page) -> bool:
    """
    检查是否真正以会员账号登录。
    "立即登录"在下拉菜单里、折叠时不可见，不可靠。
    改为：直接检测「促到课」声音卡片是否出现在我的列表中。
    """
    if "#/login" in page.url or "login" in page.url.split("#")[-1]:
        return False
    # 最可靠的判断：目标声音卡片可见 = 真实会员已登录
    try:
        found = page.evaluate("""() => {
            const walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT
            );
            let node;
            while ((node = walker.nextNode())) {
                if (node.textContent.trim() === '促到课') return true;
            }
            return false;
        }""")
        if found:
            return True
    except Exception:
        pass
    return False


# ── 调试截图 ───────────────────────────────────────────────

def _screenshot(page: Page, name: str):
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUTPUT_DIR / f"debug_{name}.png"))
    except Exception:
        pass


# ── 音频格式检测 ────────────────────────────────────────────

def _detect_audio_ext(data: bytes) -> str:
    """根据文件头字节判断真实音频格式"""
    if len(data) < 4:
        return ".mp3"
    if data[:3] == b'ID3':
        return ".mp3"
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return ".mp3"
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return ".wav"
    if data[:4] == b'OggS':
        return ".ogg"
    if data[:4] == b'fLaC':
        return ".flac"
    if data[4:8] == b'ftyp':
        return ".m4a"
    return ".mp3"


MIN_AUDIO_BYTES = 8 * 1024


def _is_probably_audio_bytes(data: bytes) -> bool:
    """过滤明显无效的短片段/伪音频响应。"""
    if not data or len(data) < MIN_AUDIO_BYTES:
        return False
    if data[:3] == b'ID3':
        return True
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return True
    if data[:4] == b'OggS':
        return True
    if data[:4] == b'fLaC':
        return True
    if data[4:8] == b'ftyp':
        return True
    # 允许无标准头但体积足够大的媒体流
    return len(data) >= 48 * 1024


# ── 登录 ───────────────────────────────────────────────────

def _ensure_logged_in(page: Page, context: BrowserContext, base_url: str,
                      on_status: Callable):
    if _load_cookies(context):
        on_status("验证 Cookie 登录态...")
        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        # SPA 可能先渲染页面再跳转至 #/login，轮询最多 10 秒
        on_status("等待声音列表加载（最多 10 秒）...")
        for _ in range(20):
            page.wait_for_timeout(500)
            if "login" in page.url.split("#")[-1]:
                break          # 已重定向到登录页，Cookie 失效
            if _is_logged_in(page):
                on_status("Cookie 有效，已自动登录")
                return
        # Cookie 无效，删掉，避免下次再用坏数据
        on_status("Cookie 已过期，重新登录...")
        try:
            COOKIES_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    on_status("正在自动登录...")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    try:
        checkbox = page.locator(".el-checkbox__inner").first
        if checkbox.is_visible(timeout=1000):
            checkbox.click()
            page.wait_for_timeout(200)
    except Exception:
        pass

    username_filled = False
    for sel in [
        'input[placeholder*="用户名"]',
        'input[placeholder*="账号"]',
        'input[placeholder*="手机"]',
        'input[placeholder*="请输入"]',
        'input[type="text"]',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click()
                page.wait_for_timeout(200)
                loc.fill("")
                loc.type(USERNAME, delay=50)
                username_filled = True
                on_status(f"已填入账号：{USERNAME}")
                break
        except Exception:
            continue

    if not username_filled:
        on_status("未找到账号框，请手动登录")

    page.wait_for_timeout(300)

    for sel in ['input[type="password"]', 'input[placeholder*="密码"]']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click()
                page.wait_for_timeout(200)
                loc.fill("")
                loc.type(PASSWORD, delay=50)
                on_status("已填入密码")
                break
        except Exception:
            continue

    page.wait_for_timeout(500)

    for sel in ['button.el-button--primary', 'button:has-text("登录")', '.login-btn']:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click()
                on_status("已点击登录，等待跳转...")
                break
        except Exception:
            continue

    # 阶段①：等待 URL 离开登录页（最多 15 秒）
    on_status("等待登录跳转...")
    for _ in range(30):
        page.wait_for_timeout(500)
        if "login" not in page.url.split("#")[-1]:
            break

    # 阶段②：跳转后导航到创建页，再等待声音列表加载
    if "login" not in page.url.split("#")[-1]:
        on_status("登录成功，正在加载声音列表...")
        if base_url not in page.url:
            page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
        for _ in range(30):
            page.wait_for_timeout(500)
            if _is_logged_in(page):
                _save_cookies(context)
                on_status("自动登录成功，Cookie 已保存")
                return

    on_status("自动登录未完成，请在浏览器中手动登录并停留在创建页面（最多 90 秒）...")
    _screenshot(page, "waiting_manual_login")
    for _ in range(180):
        page.wait_for_timeout(500)
        # 手动登录后可能跳转到其他页，强制导向创建页
        if "login" not in page.url.split("#")[-1] and base_url not in page.url:
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=10000)
            except Exception:
                pass
        if _is_logged_in(page):
            _save_cookies(context)
            on_status("登录成功，Cookie 已保存")
            return

    raise TimeoutError("等待登录超时（90 秒），请重试")


# ── 页面操作 ────────────────────────────────────────────────

def _close_popups(page: Page):
    for sel in [
        'button:has-text("关闭")',
        'button:has-text("取消")',
        '.el-dialog__headerbtn',
        '[aria-label="Close"]',
        'i.el-dialog__close',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=300):
                loc.click()
                page.wait_for_timeout(200)
        except Exception:
            pass


def _select_voice_model(page: Page, on_status: Callable):
    on_status("正在选择「促到课」声音...")

    # 等待声音列表异步加载完成
    page.wait_for_timeout(3000)

    # 找到"促到课"文字节点后，沿 DOM 向上查找真正的可点击容器
    # （Vue 的 click 事件挂在卡片 li/div 上，不在文字 span 上）
    clicked = page.evaluate("""() => {
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_TEXT
        );
        let node;
        while ((node = walker.nextNode())) {
            if (node.textContent.trim() === '促到课') {
                let el = node.parentElement;
                // 向上最多爬 6 层，找第一个 li 或 cursor:pointer 的容器
                for (let i = 0; i < 6 && el && el !== document.body; i++) {
                    const tag  = el.tagName.toLowerCase();
                    const cls  = (el.className || '').toString();
                    const cur  = window.getComputedStyle(el).cursor;
                    if (tag === 'li' ||
                        cur === 'pointer' ||
                        cls.includes('item') ||
                        cls.includes('card') ||
                        cls.includes('voice')) {
                        el.click();
                        return true;
                    }
                    el = el.parentElement;
                }
                // 兜底：点击直接父元素
                if (node.parentElement) {
                    node.parentElement.click();
                    return true;
                }
            }
        }
        return false;
    }""")

    if clicked:
        page.wait_for_timeout(800)
        on_status("已选中「促到课」声音")
        return

    # Playwright locator 最终兜底
    for sel in [
        "span:text-is('促到课')",
        "p:text-is('促到课')",
        "div:text-is('促到课')",
        "li:has-text('促到课')",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.click()
                page.wait_for_timeout(800)
                on_status("已选中「促到课」声音")
                return
        except Exception:
            continue

    _screenshot(page, "voice_not_found")
    raise RuntimeError("未找到「促到课」声音卡片（已截图：voice/output/debug_voice_not_found.png）")


def _activate_text_mode(page: Page):
    try:
        tab = page.locator("text=文本驱动").first
        if tab.is_visible(timeout=2000):
            tab.click()
            page.wait_for_timeout(400)
    except Exception:
        pass


def _fill_text(page: Page, text: str, on_status: Callable):
    on_status(f"正在填写文案（{len(text)} 字）...")

    for sel in [
        ".el-textarea__inner",
        "textarea.el-textarea__inner",
        "textarea",
        ".text-input textarea",
        "[placeholder*='文案']",
        "[placeholder*='输入']",
        "[placeholder*='文字']",
        "[placeholder*='请输入']",
        "[placeholder*='支持']",
        "[class*='content'] textarea",
        "[class*='script'] textarea",
        "div[contenteditable='true']",
    ]:
        try:
            loc = page.locator(sel).last
            if loc.is_visible(timeout=1000):
                loc.click()
                loc.fill(text)
                try:
                    # 触发前端监听，避免状态未刷新导致下一步点击无效
                    loc.dispatch_event("input")
                    loc.dispatch_event("change")
                except Exception:
                    pass
                page.wait_for_timeout(400)
                on_status(f"文案已填写（{len(text)} 字）")
                return
        except Exception:
            continue

    _screenshot(page, "textarea_not_found")
    raise RuntimeError("未找到文案输入框（已截图：voice/output/debug_textarea_not_found.png）")


# ── 音频拦截 ────────────────────────────────────────────────


def _stop_preview_if_playing(page: Page):
    """如果播放器处于试听中，先停掉，避免下一条任务状态干扰。"""
    for sel in [
        "button:has-text('试听中')",
        ".el-button:has-text('试听中')",
        "button:has-text('暂停')",
        ".vjs-play-control.vjs-playing",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=600):
                loc.click()
                page.wait_for_timeout(250)
                return
        except Exception:
            continue


def _is_preview_clickable(loc) -> bool:
    try:
        return bool(loc.evaluate("""el => {
            const btn = el.closest('button,.el-button') || el;
            const cls = (btn.className || '').toString();
            if (btn.disabled) return false;
            if (btn.getAttribute('aria-disabled') === 'true') return false;
            if (cls.includes('is-disabled')) return false;
            if (cls.includes('is-loading') || cls.includes('loading')) return false;
            return true;
        }"""))
    except Exception:
        return True


def _wait_preview_selector(page: Page, selectors: list[str], timeout_ms: int = 15000) -> str | None:
    loops = max(1, timeout_ms // 300)
    for _ in range(loops):
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=250):
                    return sel
            except Exception:
                continue
        page.wait_for_timeout(300)
    return None


def _click_preview_once(page: Page, sel: str) -> bool:
    try:
        loc = page.locator(sel).first
        if not loc.is_visible(timeout=1000):
            return False
        try:
            loc.click(timeout=2500)
            return True
        except Exception:
            try:
                loc.click(force=True, timeout=2500)
                return True
            except Exception:
                pass
        try:
            loc.evaluate("(el) => (el.closest('button,.el-button') || el).click()")
            return True
        except Exception:
            return False
    except Exception:
        return False


def _audio_hint_score(url: str, content_type: str) -> int:
    """给音频候选打分，分值越高越可能是目标 TTS 成品。"""
    score = 0
    url_l = (url or "").lower()
    ct_l = (content_type or "").lower()

    if ct_l.startswith("audio/"):
        score += 4
    if any(k in ct_l for k in ["mpeg", "mp3", "wav", "ogg", "aac", "m4a"]):
        score += 2
    if any(k in url_l for k in [".mp3", ".wav", ".ogg", ".aac", ".m4a"]):
        score += 3
    if any(k in url_l for k in ["/audio/", "/tts", "preview", "audition", "speech", "voice"]):
        score += 2
    return score


def _is_likely_tts_url(url: str) -> bool:
    u = (url or "").lower()
    if not u.startswith("http://") and not u.startswith("https://") and not u.startswith("blob:"):
        return False
    return any(k in u for k in [
        "/audition/",
        "/api/user/audition",
        "/tts",
        "/speech",
        "/audio/",
        ".mp3",
        ".wav",
        ".ogg",
        ".aac",
        ".m4a",
        "voice",
    ])


def _collect_media_urls(page: Page) -> list[str]:
    try:
        urls = page.evaluate("""() => {
            const out = [];
            const medias = Array.from(document.querySelectorAll('audio,video'));
            for (const m of medias) {
                const s1 = m.currentSrc || '';
                const s2 = m.src || '';
                if (s1) out.push(s1);
                if (s2) out.push(s2);
                const child = m.querySelector('source');
                if (child && child.src) out.push(child.src);
            }
            return Array.from(new Set(out));
        }""")
        return [u for u in (urls or []) if isinstance(u, str) and u]
    except Exception:
        return []


def _click_preview_and_capture(page: Page, on_status: Callable) -> Tuple[Optional[bytes], str]:
    """点击试听并捕获音频，返回 (data, 扩展名)"""
    on_status("等待试听按钮就绪...")

    audio_candidates: list[dict] = []
    seen_keys: set = set()
    click_ts = time.time()
    pre_media_urls = set(_collect_media_urls(page))

    def on_response(response):
        try:
            url = response.url
            content_type = response.headers.get("content-type", "")
            url_l = url.lower()
            ct_l = content_type.lower()
            score = _audio_hint_score(url_l, ct_l)
            if score <= 0 or "json" in ct_l:
                return

            data = response.body()
            if not _is_probably_audio_bytes(data):
                return

            key = (url, len(data))
            if key in seen_keys:
                return

            # 只接受点击「试听」之后到达的音频响应，避免拿到上一条任务残留请求
            now_ts = time.time()
            if now_ts + 0.01 < click_ts:
                return

            seen_keys.add(key)
            ext = _detect_audio_ext(data)
            audio_candidates.append(
                {
                    "data": data,
                    "url": url,
                    "content_type": content_type,
                    "size": len(data),
                    "score": score,
                    "ts": now_ts,
                }
            )
            on_status(f"捕获候选音频 {len(data)//1024} KB，格式：{ext}")
        except Exception:
            pass

    page.on("response", on_response)

    try:
        selectors = [
            ".right-create-box .st-part:has-text('试听')",
            ".taici-box .st-part:has-text('试听')",
            ".st-part:has-text('试听')",
            "text=试听",
            "button:has-text('试听')",
            "span:has-text('试听')",
            ".el-button:has-text('试听')",
            "[class*='preview']",
            "[class*='audition']",
        ]
        sel = _wait_preview_selector(page, selectors, timeout_ms=15000)
        if not sel:
            raise RuntimeError("未找到「试听」按钮")

        for attempt in range(2):
            on_status("点击试听，等待音频响应..." if attempt == 0 else "首次未命中，重试试听一次...")

            if not _click_preview_once(page, sel):
                raise RuntimeError("点击「试听」失败")

            click_ts = time.time()

            # 等待音频响应；单次点击后等待，避免高频点击导致播放中断
            max_rounds = 90 if attempt == 0 else 50
            last_count = len(audio_candidates)
            stable_rounds = 0
            for _ in range(max_rounds):  # 首次最多 45 秒；重试最多 25 秒
                page.wait_for_timeout(500)
                count = len(audio_candidates)
                if count <= 0:
                    continue
                if count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_count = count
                # 候选数量稳定 1.5 秒后再选，尽量拿到完整音频而不是首个短片段
                if stable_rounds >= 3:
                    break
            if audio_candidates:
                break

    finally:
        page.remove_listener("response", on_response)

    if audio_candidates:
        best = max(
            audio_candidates,
            key=lambda c: (
                c["size"],      # 优先更大体积（通常更接近完整音频）
                c["score"],     # 再看 URL/Content-Type 命中程度
                c["ts"],        # 体积和分值相同时取最新
            ),
        )
        data = best["data"]
        ext = _detect_audio_ext(data)
        on_status(
            f"音频捕获成功！格式：{ext}，来源体积 {best['size']//1024} KB（共候选 {len(audio_candidates)} 条）"
        )
        return data, ext

    # 网络事件没有命中时，尝试从播放器当前媒体源直接拉取
    try:
        media_srcs = page.evaluate("""() => {
            const rows = [];
            const medias = Array.from(document.querySelectorAll('audio,video'));
            for (const m of medias) {
                const s1 = m.currentSrc || '';
                const s2 = m.src || '';
                if (s1) rows.push({
                    src: s1,
                    paused: !!m.paused,
                    currentTime: Number(m.currentTime || 0),
                    duration: Number(m.duration || 0),
                });
                if (s2 && s2 !== s1) rows.push({
                    src: s2,
                    paused: !!m.paused,
                    currentTime: Number(m.currentTime || 0),
                    duration: Number(m.duration || 0),
                });
                const child = m.querySelector('source');
                if (child && child.src) rows.push({
                    src: child.src,
                    paused: !!m.paused,
                    currentTime: Number(m.currentTime || 0),
                    duration: Number(m.duration || 0),
                });
            }
            const unique = [];
            const seen = new Set();
            for (const r of rows) {
                if (!r.src || seen.has(r.src)) continue;
                seen.add(r.src);
                unique.push(r);
            }
            unique.sort((a, b) => {
                const aScore = (a.paused ? 0 : 2) + (a.currentTime > 0 ? 1 : 0) + (a.duration > 0 ? 1 : 0);
                const bScore = (b.paused ? 0 : 2) + (b.currentTime > 0 ? 1 : 0) + (b.duration > 0 ? 1 : 0);
                return bScore - aScore;
            });
            return unique.slice(0, 5);
        }""")
    except Exception:
        media_srcs = []

    for media in media_srcs:
        src = media.get("src") if isinstance(media, dict) else media
        if not src:
            continue
        src_l = src.lower()
        is_new_src = src not in pre_media_urls
        if not _is_likely_tts_url(src):
            continue
        # 尽量使用点击后新增的 src；旧 src 仅在明确 audition 链路时兜底
        if (not is_new_src) and ("/audition/" not in src_l) and ("/api/user/audition" not in src_l):
            continue
        try:
            if src.startswith("http://") or src.startswith("https://"):
                resp = page.context.request.get(src, timeout=15000)
                if resp.ok:
                    data = resp.body()
                    if _is_probably_audio_bytes(data):
                        ext = _detect_audio_ext(data)
                        on_status(f"播放器直取成功！格式：{ext}")
                        return data, ext
            elif src.startswith("blob:"):
                b64 = page.evaluate(
                    """async (u) => {
                        try {
                            const r = await fetch(u);
                            const b = await r.arrayBuffer();
                            if (!b || b.byteLength < 1000) return null;
                            const bytes = new Uint8Array(b);
                            let bin = '';
                            const chunk = 0x8000;
                            for (let i = 0; i < bytes.length; i += chunk) {
                                const part = bytes.subarray(i, i + chunk);
                                bin += String.fromCharCode.apply(null, part);
                            }
                            return btoa(bin);
                        } catch (e) {
                            return null;
                        }
                    }""",
                    src,
                )
                if b64:
                    data = base64.b64decode(b64)
                    if _is_probably_audio_bytes(data):
                        ext = _detect_audio_ext(data)
                        on_status(f"播放器blob提取成功！格式：{ext}")
                        return data, ext
        except Exception:
            continue

    _screenshot(page, "preview_no_audio")
    return None, ".mp3"


# ── 持久化浏览器会话 ────────────────────────────────────────

class BrowserSession:
    """
    持久化浏览器会话：登录一次，多次提交文案无需重启。
    用法：
        session = BrowserSession(url, on_status, on_done, on_ready, on_end)
        session.submit("文案内容")   # 可多次调用
        session.stop()               # 关闭浏览器
    """

    def __init__(self,
                 base_url: str,
                 on_status: Callable[[str], None],
                 on_done: Callable[[Optional[str]], None],
                 on_ready: Callable[[], None],
                 on_end: Callable[[], None]):
        self._base_url = base_url
        self._on_status = on_status
        self._on_done = on_done
        self._on_ready = on_ready   # 浏览器就绪，可以提交文案了
        self._on_end = on_end       # 浏览器彻底关闭后
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, text: str):
        """提交一条文案，加入队列"""
        self._queue.put(text)

    def stop(self):
        """关闭浏览器"""
        self._queue.put(None)

    def _run(self):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=False, slow_mo=30)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    accept_downloads=True,
                )
                context.set_default_timeout(30000)
                page = context.new_page()

                try:
                    # ① 登录（只做一次）
                    _ensure_logged_in(page, context, self._base_url, self._on_status)

                    # ② 进入创建页面
                    self._on_status("加载创建页面...")
                    if self._base_url not in page.url:
                        page.goto(self._base_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2500)
                    _close_popups(page)

                    # ③ 选声音（只做一次）
                    _select_voice_model(page, self._on_status)
                    _activate_text_mode(page)

                    # 通知 GUI 浏览器已就绪
                    self._on_status("浏览器就绪，可以生成音频了")
                    self._on_ready()

                    # ④ 循环处理文案任务
                    while True:
                        text = self._queue.get()
                        if text is None:
                            self._on_status("正在关闭浏览器...")
                            break

                        try:
                            _stop_preview_if_playing(page)
                            _activate_text_mode(page)
                            # 支持「备注::文案」格式："::" 前面作文件名，后面才是提交给TTS的文案
                            if "::" in text:
                                file_prefix, tts_text = text.split("::", 1)
                                file_prefix = file_prefix.strip() or "output"
                                tts_text = tts_text.strip()
                            else:
                                file_prefix = text[:2].strip() or "output"
                                tts_text = text
                            _fill_text(page, tts_text, self._on_status)
                            audio_bytes, ext = _click_preview_and_capture(page, self._on_status)

                            if audio_bytes:
                                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                                output_path = OUTPUT_DIR / f"{file_prefix}{ext}"
                                output_path.write_bytes(audio_bytes)
                                self._on_status(f"完成！已保存：{output_path.name}")
                                self._on_done(str(output_path.resolve()))
                            else:
                                self._on_status("未捕获到音频，请检查「试听」是否正常播放")
                                self._on_done(None)

                        except Exception as e:
                            _screenshot(page, "task_error")
                            self._on_status(f"任务错误：{e}")
                            self._on_done(None)

                except Exception as e:
                    _screenshot(page, "session_error")
                    self._on_status(f"错误：{e}")

                finally:
                    try:
                        context.close()
                        browser.close()
                    except Exception:
                        pass

        except Exception as e:
            self._on_status(f"Playwright 启动失败：{e}")
            # 写错误日志供调试（exe 模式无控制台时有用）
            try:
                import traceback
                (BASE_DIR / "error.log").write_text(
                    traceback.format_exc(), encoding="utf-8"
                )
            except Exception:
                pass

        finally:
            self._on_end()
