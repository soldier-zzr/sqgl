# AI超级分身 音频下载工具 + 云中客批量语音发送

一套完整的批量个性化语音营销自动化工具，包含三个模块：

1. **AI话术生成**（`gen_tts_agent.py`）— DeepSeek API 为每人生成个性化话术
2. **TTS音频生成**（`main.py` GUI）— 自动提交话术、拦截下载 MP3
3. **CRM批量发送**（`sender/sender.py`）— Playwright 自动发送语音到云中客 IM

---

## 完整使用流程

```
话术原料.xlsx
    │
    ▼
① GUI 里点「导入 Excel 自动生成话术」（或命令行运行 gen_tts_agent.py）
    │  DeepSeek API 生成个性化话术，自动加入任务队列
    ▼
② TTS GUI 点「开始队列」
    │  自动提交到 AI超级分身，拦截 MP3 保存到 output/
    ▼
③ python sender/sender.py
    │  Playwright 打开云中客，逐一上传发送 MP3
    ▼
完成
```

---

## 环境准备

```bash
pip install playwright customtkinter openai openpyxl
playwright install chromium
```

---

## 配置

复制配置模板并填写实际值：

```bash
cp config.example.py config.py
```

编辑 `config.py`：

```python
ACCESS_CODE      = "TTS工具登录密码"
DEEPSEEK_API_KEY = "sk-xxxxxxxx"       # https://platform.deepseek.com
CRM_PHONE        = "手机号@姓名"        # 云中客账号
CRM_PASSWORD     = "密码"
```

---

## 模块说明

### 一、准备 `话术原料.xlsx`

| 姓名 | 赛道 | 备注 |
|------|------|------|
| 张三 | 知识付费 | 起盘营4期260302张三 |
| 李四 | 电商 | 起盘营4期260302李四 |

- **姓名**：用于 AI 生成话术中称呼对方
- **赛道**：用于个性化话术（留空则使用通用模板）
- **备注**：MP3 文件名，必须与云中客好友备注一致（唯一标识）

### 二、生成话术 + MP3

**推荐：GUI 一键完成**

```bash
python main.py
```

输入访问密码后：
1. 点击「导入 Excel 自动生成话术」→ 选择 `话术原料.xlsx`
2. 等待状态栏显示"已加入 N 条任务"
3. 点「开启浏览器」→ 点「开始队列」
4. 等待所有任务状态变为绿色（成功）

**命令行分步执行**

```bash
python gen_tts_agent.py   # 生成 tts_input.txt
python main.py             # 打开 GUI，粘贴内容，开始队列
```

### 三、调试 / 修改 AI 提示词

直接编辑 `prompt.txt`，保存后下次生成自动读取，无需改代码。

### 四、批量发送到云中客

配置 `sender/sender.py` 顶部配置区：

```python
VOICE_DIR  = ...           # 默认 ../output，通常无需修改
EXCEL_FILE = Path("好友数据_xxx.xlsx")  # 从云中客导出的好友列表（A列昵称 B列备注）
MAX_SEND   = None          # None 不限制；设数字防误操作
```

运行：

```bash
python sender/sender.py
```

首次运行或 session 过期时会自动登录，登录态保存到 `sender/session.json`。

---

## 文件结构

```
voice/
├── config.example.py     # 配置模板（复制为 config.py 后填写）
├── config.py             # 实际配置（已 gitignore，不提交）
├── prompt.txt            # AI 话术提示词（可直接编辑）
├── 话术原料.xlsx          # 待发送名单模板（姓名+赛道+备注）
├── main.py               # TTS 工具启动入口
├── browser.py            # TTS 自动化核心（Playwright）
├── gen_tts_agent.py      # DeepSeek 话术生成智能体
├── gen_tts_input.py      # 静态话术合并工具（备用）
├── ui/
│   ├── app.py            # GUI 主界面
│   ├── models.py         # 任务数据模型
│   ├── queue_manager.py  # 队列管理
│   └── theme.py          # 颜色主题
├── utils/
│   └── naming.py         # MP3 命名（支持 备注::话术 格式）
├── output/               # 生成的 MP3（已 gitignore）
└── sender/
    ├── sender.py         # 云中客批量发送脚本
    └── session.json      # CRM 登录态（已 gitignore，本地保留）
```

---

## 注意事项

- `config.py`、`*.xlsx`、`session.json`、`output/` 均已加入 `.gitignore`，不会提交
- `prompt.txt` 已提交，修改后 push 即可同步给团队
- 若 session 过期，删除 `sender/session.json` 重新运行即可
- MP3 若生成后发现文件名有 BOM 字符（`\ufeff`），运行以下修复：

  ```python
  import os; d = "output"
  for f in os.listdir(d):
      if f.startswith('\ufeff'):
          os.rename(f"{d}/{f}", f"{d}/{f.lstrip(chr(0xfeff))}")
  ```

---

## Claude Code 快速上手

用 Claude Code 打开本项目后，可以直接说：

- "帮我修改提示词，改成 XXX 风格"
- "批量发送失败了，看看 sender.py 的日志"
- "新增功能：发完后在 Excel 里标记已发送"
