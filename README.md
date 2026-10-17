# reddit-cli (Enhanced)

> 在终端里极速刷 Reddit，自动并发翻译成中文。不开浏览器，不离开命令行。支持任意社区直达、多级评论树、无限分页与原生回帖。

```text
┌─ worldnews · 🔥 热门 ────────────────────────────────────────────────────────┐
│                                                                              │
│  [1] 🔥 热门   [2] 🕒 最新   [3] 🏆 最高   [4] 📈 上升     Tab: 循环切换     │
│                                                                              │
│  1. 乌克兰宣布与欧盟签署历史性安全协议                    ↑42.3k  💬 8.2k  3h │
│  2. 日本央行意外加息，日元大幅升值                        ↑31.1k  💬 5.4k  5h │
│  3. 科学家首次在火星土壤中发现有机分子                    ↑28.7k  💬 3.1k  6h │
│  4. 苹果宣布将在印度建设最大海外研发中心                  ↑19.2k  💬 2.8k  8h │
│  5. 联合国报告：全球极端天气事件频率创历史新高            ↑15.6k  💬 4.2k  9h │
│                                                                              │
│  ┌ u/throwaway_news · ↑12.4k                                                │
│  │ 这是近十年来最重要的外交突破之一，意味着乌克兰正式进入欧洲安全体系...   │
│  ╰ u/commenter_one · ↑3.1k                                                  │
│    ↳ u/sub_reply · ↑850                                                     │
│                                                                              │
└─ [↑↓]导航  [Enter]查看  [t]原文/译文  [c]回帖  [s]切排序  [/]搜索  [q]退出 ─┘
```

---

## ✨ 核心特性

- **终端沉浸体验** — 全程键盘快捷键流，沉浸式刷帖，写代码或看终端时无缝切换。
- **全语言并发中文翻译** — 标题、正文、各层级评论全部后台 8 线程并发翻译，先瞬时显示排版与原文，再逐条平滑替换，彻底告别卡顿。
- **按 `t` 键双语秒切** — 浏览列表或深入长篇讨论时，按 `t` 键随时在**中文译文**与**原始外文**之间无感切换对照。
- **任意板块秒开** — 命令行直接传参（`reddit <subreddit>`），或在搜索框输入任意社区名敲回车直达。
- **可视化排序切换** — 顶部直观展示 `[1] 🔥 热门`、`[2] 🕒 最新`、`[3] 🏆 最高`、`[4] 📈 上升`，支持数字键、Tab 键或鼠标切换。
- **无限下拉分页** — 打通 Reddit API 的 `after` 分页机制，滚动到底部自动异步拉取下一批帖子。
- **多层递归评论树** — 彻底解决原版仅看前 20 条、丢弃深层回复的痛点。深度支持 **10 层递归树状展开**，单帖默认拉取最高 500 条节点，`┌` 主楼、`╰` 一级回复、`↳` 二级及更深楼中楼层级清晰，一条不漏。
- **原生回帖与发评 (`c` 键)** — 按 `c` 键呼出回帖弹窗，支持回复主贴，或下拉精准挑选某条评论楼层回复；原生打通 Reddit Cookie 与系统 `opencli` 登录凭据。
- **智能代理自适应** — 自动嗅探 macOS 系统代理与本地科学上网端口（1082 / 7890 / 7897 等），支持 `-p` 显式指定代理。

---

## 📦 安装

推荐使用现代 Python CLI 包管理器安装（环境完全隔离，秒级完成）：

### 方式 1：使用 `uv` 安装（最推荐，极速）
```bash
# 首次安装
uv tool install git+https://github.com/leilintao/reddit-cli.git

# 若之前安装过，覆盖更新
uv tool install --force git+https://github.com/leilintao/reddit-cli.git
```

### 方式 2：使用 `pipx` 安装
```bash
pipx install git+https://github.com/leilintao/reddit-cli.git --force
```

### 方式 3：普通 `pip` 安装
```bash
pip install git+https://github.com/leilintao/reddit-cli.git
```

---

## 🚀 怎么用

```bash
# 1. 启动并进入板块大厅导航
reddit

# 2. 命令行直接秒开指定社区（支持带或不带 r/）
reddit turkey
reddit r/technology
reddit wallstreetbets

# 3. 纯英文原生模式（禁用自动中文翻译）
reddit turkey -T

# 4. 手动指定代理（当系统代理不稳定时）
reddit -p http://127.0.0.1:1082 china_irl

# 5. 查看当前 Reddit 登录账号（回帖发评凭据）
reddit --whoami

# 6. 配置/更新 Reddit Cookie (reddit_session)
reddit -c "<reddit_session_cookie>"
```

---

## ⌨️ 完整键位表（Keybindings）

| 快捷键 | 功能说明 | 适用界面 |
| :--- | :--- | :--- |
| `↑` `↓` 或 `j` `k` | 上下移动光标（接近底部时自动触发追加加载） | 板块列表 / 帖子列表 / 评论区 |
| `Enter` (回车) | 进入板块 / 打开帖子详情 / 底部手动加载更多 | 全局 |
| `Esc` / `Backspace` | 返回上一级（详情页 → 帖子列表 → 社区选择） | 全局 |
| `t` | **🌐 切换原文与译文**（即时中英无感切换） | 帖子列表页 / 帖子详情页 |
| `c` | **💬 回帖 / 发表评论**（回复主贴或下拉精准选楼层） | 帖子列表页 / 帖子详情页 |
| `Ctrl+S` / `Ctrl+J` | **确认发送评论** | 回帖弹窗 |
| `1` `2` `3` `4` | 快速切换帖子排序模式（1: 热门 / 2: 最新 / 3: 最高 / 4: 上升） | 帖子列表页 |
| `Tab` | 循环切换下一个帖子排序模式 | 帖子列表页 |
| `鼠标点击` | 可直接点击顶部排序标签切换 | 帖子列表页 |
| `/` | 在当前板块内搜索关键字帖子 | 帖子列表页 |
| `r` | **手动刷新**（列表页刷新列表；详情页重新拉取评论） | 帖子列表页 / 帖子详情页 |
| `s` | **🔀 切换评论排序**（🔥最佳 → 🏆最高分 → 🕒最新 → ⚡争议） | 帖子详情页 |
| `m` / `a` | **⏬ 追加更多 / 一键全量评论**（支持追加至 1500 条） | 帖子详情页 |
| `o` | 使用系统默认浏览器打开当前 Reddit 帖子网页 | 帖子详情页 |
| `q` | 退出程序 | 全局 |

---

## 🛠️ 技术细节

- **无需官方 API Key** — 浏览通道基于 Reddit 公开 JSON 接口，免登录开箱即用。
- **并发与缓存翻译流水线** — 8 线程线程池并发请求，集成 Google GTX 极速引擎与多层降级，搭载内存级去重缓存，切换排序与展开评论秒出不卡顿。
- **树状评论解析器** — 递归遍历 Reddit JSON 响应，解析深达 10 层嵌套讨论，自动过滤机器人与 Moderator 评论，规整 Markdown 链接格式。
- **安全认证与发帖通道** — 支持 `reddit_session` Cookie 直连提交或无缝复用本机 `opencli` 凭证。

依赖：[Textual](https://github.com/Textualize/textual) · [deep-translator](https://github.com/nidhaloff/deep-translator) · [requests](https://github.com/psf/requests) · [click](https://github.com/pallets/click)

---

## 💻 本地二次开发

```bash
git clone https://github.com/leilintao/reddit-cli.git
cd reddit-cli
pip install -e .
reddit
```

---

## License

MIT License
