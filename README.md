# reddit-cli

终端里的 Reddit 浏览器，支持中文翻译。

![Version](https://img.shields.io/badge/version-0.2.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## 特性

- 🎯 **三级导航** — 板块选择 → 帖子列表 → 详情+评论
- 🌏 **中文翻译** — 自动翻译标题、正文、评论（Google Translate）
- ⚡ **渐进式加载** — 先显示原文，翻译完成后逐条替换，体验流畅
- 🎨 **TUI 界面** — 基于 Textual，支持键盘导航
- 🔍 **搜索功能** — 在板块内搜索关键词
- 🤖 **过滤 Bot** — 自动过滤机器人评论
- 📱 **分类板块** — 预设新闻、科技、娱乐等常用板块

## 安装

```bash
pip install git+https://github.com/osen7/reddit-cli.git
```

或本地安装：

```bash
git clone https://github.com/osen7/reddit-cli.git
cd reddit-cli
pip install -e .
```

## 使用

```bash
reddit
```

启动后进入板块选择页，选择感兴趣的板块即可浏览。

## 键位

| 键 | 功能 |
|----|------|
| `↑` / `↓` / `j` / `k` | 上下导航 |
| `Enter` | 进入 / 选择 |
| `Esc` / `Backspace` | 返回上一级 |
| `Tab` | 切换排序（热门/最新/最高/上升） |
| `/` | 搜索帖子 |
| `s` | 切换板块 |
| `r` | 刷新 |
| `o` | 浏览器打开当前帖子 |
| `q` | 退出 |

## 预设板块

- 📰 新闻与时事：worldnews, news, politics, geopolitics
- 💻 科技：technology, programming, MachineLearning, Python
- 🎮 游戏与娱乐：gaming, funny, movies, music, anime
- 💬 讨论与学习：AskReddit, todayilearned, explainlikeimfive
- 🌏 中文相关：China, China_irl, CHNEWS
- 📈 财经：wallstreetbets, investing, CryptoCurrency
- 🔬 科学：science, space, physics, biology

## 技术栈

- [Textual](https://github.com/Textualize/textual) — TUI 框架
- [deep-translator](https://github.com/nidhaloff/deep-translator) — Google 翻译
- [requests](https://github.com/psf/requests) — HTTP 请求
- [click](https://github.com/pallets/click) — CLI 参数解析

## 开发

```bash
git clone https://github.com/osen7/reddit-cli.git
cd reddit-cli
pip install -e .
reddit
```

## 许可

MIT License

## 致谢

Co-developed with Claude Sonnet 4.6
