# AI超级分身 音频下载工具

基于 Playwright 浏览器自动化，批量将文案提交至 AI 超级分身平台生成语音，并自动捕获、保存音频文件。

---

## 功能特性

- **批量队列处理**：粘贴多行文案，自动逐条生成音频
- **智能音频捕获**：通过网络拦截实时抓取 TTS 音频，无需手动操作
- **访问密码保护**：启动时验证密码，防止未授权使用
- **进度可视化**：队列状态实时更新（成功 / 失败 / 待处理）
- **一键打开输出目录**：音频文件自动保存，支持快速定位

---

## 项目结构

```
voice/
├── main.py                 # 启动入口（含访问密码验证）
├── browser.py              # Playwright 浏览器自动化 & 音频捕获核心
├── config.example.py       # 配置文件模板（复制为 config.py 后填写密码）
├── ui/
│   ├── app.py              # 主界面（CustomTkinter）
│   ├── models.py           # 队列数据模型
│   ├── queue_manager.py    # 队列管理逻辑
│   └── theme.py            # 界面主题配置
├── utils/
│   └── naming.py           # 输出文件命名工具
├── logo.ico                # 应用图标（原始）
├── make_icon.py            # 图标生成脚本
├── AI音频下载工具.spec      # PyInstaller 打包配置
└── output/                 # 音频输出目录（自动生成，已忽略）
```

---

## 环境依赖

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.13 |
| customtkinter | 5.x | 现代化 Tkinter UI |
| playwright | 1.x | 浏览器自动化 |
| Pillow | 任意 | 图标处理（仅打包时需要）|

安装依赖：

```bash
pip install customtkinter playwright pillow
python -m playwright install chromium
```

---

## 快速开始

### 1. 配置访问密码

```bash
cp config.example.py config.py
```

编辑 `config.py`，将 `your_password_here` 改为实际密码：

```python
ACCESS_CODE = "your_password_here"
```

> `config.py` 已加入 `.gitignore`，不会被提交到仓库。

### 2. 运行程序

```bash
python main.py
```

启动后弹出密码验证窗口，输入正确密码后进入主界面。

### 3. 使用流程

1. 点击 **开启浏览器** → 等待浏览器自动登录平台
2. 在左侧文本框粘贴文案（每行一条）
3. 点击 **加入队列**
4. 点击 **开始队列** → 自动逐条处理
5. 处理完成后点击 **打开输出目录** 查看音频文件

---

## 打包为 EXE

### 前置准备

确保打包所用的 Python 环境已安装所有依赖：

```bash
pip install pyinstaller customtkinter playwright pillow
python -m playwright install chromium
```

### 生成图标

```bash
python make_icon.py
```

会在当前目录生成 `logo.png` 和 `logo_fixed.ico`。

### 执行打包

```bash
pyinstaller "AI音频下载工具.spec" --noconfirm
```

> 打包完成后，可分发目录为 `dist/AI音频下载工具/`（需整个文件夹一起压缩发送，不能只发 `.exe`）。

---

## 配置说明

### config.py（不提交到 git）

```python
ACCESS_CODE = "your_password_here"   # 软件启动密码
```

### 目标平台

程序默认对接的平台地址在 `ui/app.py` 中的 `BASE_URL` 变量，按需修改。

---

## 常见问题

**Q：浏览器打开后一直卡在登录页？**
A：平台登录状态存储在 `cookies.json`，首次使用需手动登录一次，之后会自动复用。

**Q：音频捕获失败？**
A：检查平台的「试听」按钮是否正常显示，网络是否畅通。状态栏会显示详细进度。

**Q：EXE 双击无反应？**
A：确保 `_internal/` 目录和 `AI音频下载工具.exe` 在同一文件夹下，不能单独运行 exe。

**Q：更换平台账号？**
A：删除 `cookies.json` 后重启程序，重新手动登录即可。

---

## 注意事项

- `cookies.json` 包含登录凭证，**请勿提交到 git 或分享给他人**
- 音频输出默认保存在 `output/` 目录，文件名取文案前两字
- 建议每次修改代码后重新执行打包流程，确保 exe 与源码同步
