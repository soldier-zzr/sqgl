"""
云中客 IM 批量语音发送脚本 v2.0

流程：
  [1] +号 → 搜索联系人（用昵称A列）→ 创建/缓存会话
  [2] 左侧搜索 → 精准定位并打开会话（用昵称A列）
  [3] icon-Frame1 → 选机器人 → 上传MP3 → 保存 → 选择 → 发送语音

文件命名规则：VOICE_DIR / {备注B列}.mp3
  例：备注 = 起盘营4期260302soldier → 找 起盘营4期260302soldier.mp3

联系人来源：EXCEL_FILE 的 A列(昵称) + B列(备注)
  也可将 EXCEL_FILE 设为 None，直接用下方 TARGET_NAMES 手动指定
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def load_contacts_from_excel(excel_path: Path) -> list[tuple[str, str]]:
    """从 Excel 读取联系人列表，返回 [(昵称A列, 备注B列), ...]"""
    try:
        import openpyxl
    except ImportError:
        print("[ERR] 缺少 openpyxl，请运行: pip install openpyxl")
        return []

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active
    contacts = []
    for row in ws.iter_rows(min_row=2, values_only=True):  # 跳过表头
        nickname = str(row[0]).strip() if row[0] else ""   # A列：昵称
        remark   = str(row[1]).strip() if row[1] else ""   # B列：备注
        if nickname and remark:
            contacts.append((nickname, remark))
    print(f"从 Excel 读取到 {len(contacts)} 个联系人")
    return contacts

# ======================== 配置区 ========================

# MP3 文件目录（文件名 = 备注.mp3）
# 指向 TTS 工具的 output 目录
VOICE_DIR = Path(__file__).resolve().parent.parent / "output"

# 好友数据 Excel（A列=昵称，B列=备注）
# 从云中客导出的好友列表；设为 None 则使用下方 TARGET_NAMES
EXCEL_FILE: Path | None = None
# EXCEL_FILE = Path(r"好友数据_20260305T125413.xlsx")  # 取消注释并修改路径

# 手动指定联系人（当 EXCEL_FILE = None 时使用）
# 格式：(昵称, 备注)，昵称用于CRM搜索，备注用于找MP3文件
TARGET_NAMES: list[tuple[str, str]] = [
    # ("Soldier", "起盘营4期260302soldier"),
]

# 最多发送几个（防误操作；设为 None 则不限制）
MAX_SEND: int | None = None

# 每个联系人发完后等待秒数
DELAY_BETWEEN = 3.0

# 调试截图（正式运行可改为 False）
DEBUG_SCREENSHOT = False

# ========================================================

SESSION_FILE = Path(__file__).parent / "session.json"
IM_URL = "https://cms.iyunzk.com/im/"

# 凭证：优先从 config.py 读取
try:
    from config import CRM_PHONE as PHONE, CRM_PASSWORD as PASSWORD  # type: ignore
except ImportError:
    PHONE    = ""  # 请在 config.py 中设置 CRM_PHONE
    PASSWORD = ""  # 请在 config.py 中设置 CRM_PASSWORD


def do_login(page: Page):
    page.goto("https://cms.iyunzk.com", timeout=30000)
    time.sleep(2)
    page.locator("input").nth(0).fill(PHONE)
    page.locator("input").nth(1).fill(PASSWORD)
    page.locator(".from-line-btn:not(.plain)").first.click()
    page.wait_for_url("**/cms**", timeout=15000)
    time.sleep(1)
    for sel in [".drainage-dialog-mask", "[class*=dialog-mask]"]:
        try:
            if page.locator(sel).first.is_visible(timeout=2000):
                page.locator(sel).first.click(force=True)
                time.sleep(0.5)
        except Exception:
            pass
    print("登录成功")


def screenshot(page: Page, name: str):
    if DEBUG_SCREENSHOT:
        path = f"debug_{name}.png"
        page.screenshot(path=path)


# ── 步骤1a：打开 + 对话框 ────────────────────────────────

def open_create_dialog(page: Page) -> bool:
    plus_btn = page.locator(".el-icon-plus").nth(1)
    try:
        plus_btn.wait_for(state="visible", timeout=5000)
        plus_btn.click()
        page.locator(".session-dialog").last.wait_for(state="visible", timeout=5000)
        time.sleep(1)
        return True
    except Exception as e:
        print(f"  [ERR] 打开+对话框失败: {e}")
        return False


# ── 步骤1b：在 + 对话框中搜索并勾选联系人 ───────────────

def search_and_select(page: Page, keyword: str) -> bool:
    dialog = page.locator(".session-dialog").last
    search = dialog.locator("input.el-input__inner:not([readonly])").nth(1)
    try:
        search.wait_for(state="visible", timeout=5000)
    except Exception:
        print("  [ERR] 找不到搜索框")
        return False

    # 等对话框完全稳定后再输入（防止部分按键丢失）
    time.sleep(1.5)
    search.click()
    time.sleep(0.5)
    search.fill("")
    time.sleep(0.3)
    search.type(keyword, delay=80)
    search.press("Enter")
    time.sleep(0.3)
    try:
        dialog.locator(".el-icon-search").first.click(timeout=1000)
    except Exception:
        pass

    try:
        page.locator(".el-loading-spinner").wait_for(state="hidden", timeout=5000)
    except Exception:
        pass
    time.sleep(1.0)
    screenshot(page, f"search_{keyword}")

    first_row = dialog.locator("tr.el-table__row").first
    try:
        first_row.wait_for(state="visible", timeout=5000)
    except Exception:
        # 尝试首字母大写重试（应对昵称大小写不一致）
        alt = keyword.capitalize()
        if alt != keyword:
            search.fill("")
            time.sleep(0.3)
            search.type(alt, delay=80)
            search.press("Enter")
            time.sleep(0.3)
            try:
                dialog.locator(".el-icon-search").first.click(timeout=1000)
            except Exception:
                pass
            try:
                page.locator(".el-loading-spinner").wait_for(state="hidden", timeout=5000)
            except Exception:
                pass
            time.sleep(1.0)
            try:
                first_row.wait_for(state="visible", timeout=5000)
            except Exception:
                print(f"  [WARN] 未找到联系人: {keyword}")
                return False
        else:
            print(f"  [WARN] 未找到联系人: {keyword}")
            return False

    first_row.locator(".el-checkbox__inner").first.click()
    time.sleep(0.8)
    screenshot(page, f"selected_{keyword}")
    return True


# ── 步骤1c：点下一步 + 确认创建 ─────────────────────────

def confirm_create_session(page: Page) -> bool:
    dialog = page.locator(".session-dialog").last
    btn = dialog.locator("button:has-text('下一步')")
    try:
        btn.wait_for(state="visible", timeout=3000)
        btn.click()
        time.sleep(1.5)
        screenshot(page, "next_step")
    except Exception as e:
        print(f"  [ERR] 点下一步失败: {e}")
        return False

    # 「确认创建会话」子对话框
    confirm = page.locator(".el-dialog:has-text('确认创建会话')")
    try:
        confirm.wait_for(state="visible", timeout=3000)
        confirm.locator("button:has-text('确认创建会话')").click()
        time.sleep(2.5)
        screenshot(page, "confirm_create")
        return True
    except Exception:
        pass

    # 若提示「会话已存在」，直接当作成功
    try:
        body_txt = page.locator(".el-message-box, .el-dialog").last.inner_text(timeout=1000)
        if "已存在" in body_txt or "already" in body_txt.lower():
            print("  会话已存在，跳过创建")
            try:
                page.locator(".el-message-box__btns button, .el-dialog button:has-text('确定')").first.click()
            except Exception:
                pass
            return True
    except Exception:
        pass

    # 若有错误提示
    try:
        err = dialog.locator(".el-form-item__error")
        if err.first.is_visible(timeout=800):
            print(f"  [ERR] {err.first.inner_text().strip()}")
            return False
    except Exception:
        pass

    return True


# ── 步骤2：左侧🔍搜索，精准定位并打开会话 ───────────────

def search_and_open_session(page: Page, keyword: str) -> bool:
    search_icon = page.locator(".session-tool-saerch").locator("i").first
    clicked = False
    try:
        search_icon.wait_for(state="visible", timeout=5000)
        search_icon.click()
        clicked = True
        time.sleep(1.2)
    except Exception:
        pass

    if not clicked:
        for x, y in [(297, 58), (310, 55), (280, 60)]:
            page.mouse.click(x, y)
            time.sleep(1.0)
            if page.locator("input.el-input__inner:not([readonly])").count() > 1:
                break

    # 找搜索输入框
    search_input = None
    for sel in [
        ".session-tool-saerch input",
        ".session-body input.el-input__inner",
        ".session-tool input",
        ".session input",
        "input[placeholder*='人名']",
        "input[placeholder*='搜索']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                search_input = loc
                break
        except Exception:
            pass

    if search_input is None:
        print("  [ERR] 搜索输入框未出现")
        screenshot(page, "search_input_not_found")
        return False

    search_input.fill("")
    search_input.type(keyword, delay=80)
    print("  等待搜索结果缓存…")
    time.sleep(3.0)
    try:
        page.locator(".el-loading-spinner").wait_for(state="hidden", timeout=6000)
    except Exception:
        pass
    time.sleep(0.5)
    screenshot(page, f"left_search_{keyword}")

    # 只匹配会话名字字段（不匹配副标题）
    items = page.locator(".session-item").all()
    target_item = None
    for item in items:
        try:
            name_txt = item.locator(".session-data-name-text").inner_text(timeout=500).strip()
            if keyword.lower() in name_txt.lower():
                print(f"  精准匹配: {name_txt!r}")
                target_item = item
                break
        except Exception:
            pass

    if target_item is None:
        print(f"  [WARN] 未在搜索结果中找到 {keyword}（共 {len(items)} 项）")
        return False

    target_item.click()
    print("  等待聊天窗口加载…")
    time.sleep(2.5)

    try:
        search_input.fill("")
        page.keyboard.press("Escape")
        time.sleep(0.8)
    except Exception:
        pass

    screenshot(page, f"session_opened_{keyword}")
    return True


# ── 步骤3：上传并发送语音 ────────────────────────────────

def upload_voice(page: Page, mp3_path: Path) -> bool:
    if not mp3_path.exists():
        print(f"  [ERR] 文件不存在: {mp3_path}")
        return False

    time.sleep(2.5)

    # 点工具栏语音图标（icon-Frame1）
    voice_icon = page.locator(".iconfont.icon-Frame1").first
    try:
        voice_icon.wait_for(state="visible", timeout=5000)
        voice_icon.click()
        time.sleep(1.5)
        screenshot(page, "voice_dialog_open")
    except Exception as e:
        print(f"  [ERR] 点语音图标失败: {e}")
        return False

    # 选择机器人
    print("  选择机器人…")
    robot_select = page.locator(".el-dialog .el-select").first
    try:
        robot_select.click(timeout=3000)
        time.sleep(0.8)
        first_opt = page.locator(".el-select-dropdown__item").first
        first_opt.wait_for(state="visible", timeout=3000)
        first_opt.click()
        print("  等待语音列表加载…")
        time.sleep(3.0)
        try:
            page.locator(".el-loading-spinner").wait_for(state="hidden", timeout=8000)
        except Exception:
            pass
        time.sleep(1.0)
        screenshot(page, "robot_selected")
    except Exception as e:
        print(f"  [WARN] 机器人选择失败: {e}")

    # 点▼展开，选「上传MP3文件」
    caret_clicked = False
    for caret_sel in [
        ".el-dialog .el-dropdown__caret-button",
        ".el-dialog .el-button-group .el-dropdown__caret-button",
        ".el-dialog .el-button-group button:last-child",
    ]:
        try:
            caret = page.locator(caret_sel).first
            caret.wait_for(state="visible", timeout=2000)
            caret.click()
            caret_clicked = True
            break
        except Exception:
            pass

    if not caret_clicked:
        page.evaluate("""
            const btns = document.querySelectorAll('.el-dialog .el-button-group button');
            if (btns.length >= 2) btns[btns.length-1].click();
        """)

    time.sleep(1.0)

    # 点「上传MP3文件」菜单项（JS备用）
    menu_item = page.locator(".el-dropdown-menu__item").filter(has_text="MP3")
    try:
        menu_item.wait_for(state="visible", timeout=4000)
        menu_item.click()
    except Exception:
        page.evaluate("""
            const items = document.querySelectorAll('.el-dropdown-menu__item');
            for (const item of items) {
                if (item.textContent.includes('MP3')) { item.click(); break; }
            }
        """)
    time.sleep(1.0)
    screenshot(page, "voice_upload_dialog")

    # 点「点击上传」触发文件选择
    click_upload_link = page.locator("a:has-text('点击上传'), span:has-text('点击上传')")
    try:
        click_upload_link.wait_for(state="visible", timeout=3000)
    except Exception:
        print("  [ERR] 未找到「点击上传」链接")
        screenshot(page, "upload_error")
        return False

    with page.expect_file_chooser(timeout=6000) as fc_info:
        click_upload_link.click()
    fc_info.value.set_files(str(mp3_path))
    print(f"  已选择文件: {mp3_path.name}")
    time.sleep(1.5)

    # 点「保存」
    save_btn = page.locator("button:has-text('保存')")
    try:
        save_btn.wait_for(state="visible", timeout=5000)
        save_btn.click()
        time.sleep(2.0)
    except Exception:
        print("  [WARN] 未找到「保存」按钮")
    time.sleep(2)

    # 点「选择」
    try:
        page.locator("button:has-text('选择')").first.wait_for(state="visible", timeout=15000)
        page.locator("button:has-text('选择')").first.click()
        time.sleep(1.5)
        screenshot(page, "after_select_voice")
    except Exception:
        print("  [WARN] 未找到「选择」按钮")

    # 关闭采集语音对话框
    try:
        close_btn = page.locator(".el-dialog__close").first
        if close_btn.is_visible(timeout=1000):
            close_btn.click()
            time.sleep(0.8)
    except Exception:
        pass

    # 点「发送语音」真正发出
    print("  点击「发送语音」…")
    send_btn = page.locator("button:has-text('发送语音')")
    try:
        send_btn.wait_for(state="visible", timeout=5000)
        send_btn.click()
        print("  语音已发送！")
        time.sleep(2.0)
        screenshot(page, "after_send")
    except Exception as e:
        print(f"  [WARN] 点「发送语音」失败: {e}")
        screenshot(page, "send_fail")

    return True


# ── 主流程 ───────────────────────────────────────────────

def send_voice_to_contact(page: Page, nickname: str, remark: str) -> bool:
    """
    nickname : A列昵称，用于 CRM +号搜索 和 左侧会话匹配
    remark   : B列备注，用于定位 MP3 文件（文件名 = remark.mp3）
    """
    mp3_path = VOICE_DIR / f"{remark}.mp3"

    # [1] +号创建/缓存会话
    print(f"  [1] +号创建会话: {nickname}")
    if not open_create_dialog(page):
        return False
    if not search_and_select(page, nickname):
        try:
            page.locator(".el-dialog__close").first.click()
        except Exception:
            pass
        return False
    if not confirm_create_session(page):
        return False

    # 等对话框彻底关闭
    try:
        page.locator(".session-dialog").last.wait_for(state="hidden", timeout=8000)
        print("  对话框已关闭")
    except Exception:
        pass
    time.sleep(1.5)

    # [2] 左侧搜索打开会话
    print(f"  [2] 搜索并打开会话: {nickname}")
    if not search_and_open_session(page, nickname):
        return False

    # [3] 上传并发送语音
    print(f"  [3] 上传语音: {mp3_path.name}")
    if not upload_voice(page, mp3_path):
        return False

    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=80)

        if SESSION_FILE.exists():
            ctx = browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport={"width": 1600, "height": 900},
            )
            print(f"已加载 session: {SESSION_FILE}")
        else:
            ctx = browser.new_context(viewport={"width": 1600, "height": 900})
            print("未找到 session.json，将自动登录…")

        page = ctx.new_page()
        page.goto(IM_URL, timeout=30000)
        time.sleep(2)

        # 检测 session 是否过期
        needs_login = False
        if "login" in page.url or "cms.iyunzk.com" not in page.url:
            needs_login = True
        else:
            try:
                page.locator("button:has-text('登录')").first.wait_for(state="visible", timeout=3000)
                needs_login = True
                print("session已过期，重新登录…")
            except Exception:
                pass
        if needs_login:
            do_login(page)
            page.goto(IM_URL, timeout=30000)
            time.sleep(3)

        print(f"IM 页面已加载: {page.url}")
        time.sleep(3)

        # 读取联系人列表
        if EXCEL_FILE and EXCEL_FILE.exists():
            contacts = load_contacts_from_excel(EXCEL_FILE)
        else:
            contacts = list(TARGET_NAMES)
            if EXCEL_FILE:
                print(f"[WARN] Excel 文件不存在: {EXCEL_FILE}，使用 TARGET_NAMES")

        # 只保留有 MP3 文件的联系人
        contacts = [(n, r) for n, r in contacts if (VOICE_DIR / f"{r}.mp3").exists()]
        print(f"  其中有 MP3 文件的: {len(contacts)} 人")

        if MAX_SEND is not None:
            contacts = contacts[:MAX_SEND]

        if not contacts:
            print("[ERR] 联系人列表为空，退出")
        else:
            print(f"本次发送 {len(contacts)} 人")

        sent_count = 0
        failed = []

        for i, (nickname, remark) in enumerate(contacts):
            print(f"\n[{i+1}/{len(contacts)}] -> {nickname}  (MP3: {remark}.mp3)")
            mp3 = VOICE_DIR / f"{remark}.mp3"
            if not mp3.exists():
                print(f"  [SKIP] MP3 不存在: {mp3}")
                failed.append(f"{nickname}({remark}.mp3 missing)")
                continue
            ok = send_voice_to_contact(page, nickname, remark)
            if ok:
                sent_count += 1
                print("  [OK] 完成")
            else:
                failed.append(nickname)
                print("  [FAIL] 失败")
            if i < len(contacts) - 1:
                time.sleep(DELAY_BETWEEN)

        ctx.storage_state(path=str(SESSION_FILE))
        ctx.close()
        browser.close()

    print(f"\n{'='*40}")
    print(f"完成  成功: {sent_count}  失败/跳过: {len(failed)}")
    if failed:
        print("失败/跳过列表:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
