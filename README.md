# reddit-cli

> 在终端里刷 Reddit，自动翻译成中文。不开浏览器，不离开命令行。

```
┌─ worldnews · 热门 ──────────────────────────────────────────────────────────┐
│                                                                              │
│  1. 乌克兰宣布与欧盟签署历史性安全协议                    ↑42.3k  💬 8.2k  3h │
│  2. 日本央行意外加息，日元大幅升值                        ↑31.1k  💬 5.4k  5h │
│  3. 科学家首次在火星土壤中发现有机分子                    ↑28.7k  💬 3.1k  6h │
│  4. 苹果宣布将在印度建设最大海外研发中心                  ↑19.2k  💬 2.8k  8h │
│  5. 联合国报告：全球极端天气事件频率创历史新高            ↑15.6k  💬 4.2k  9h │
│                                                                              │
│  ┌ u/throwaway_news · ↑12.4k                                                │
│  │ 这是近十年来最重要的外交突破之一，意味着乌克兰正式                          │
│  │ 进入欧洲安全体系，俄罗斯的战略空间将被进一步压缩...                         │
│  └                                                                           │
└─ [↑↓]导航  [Enter]查看  [/]搜索  [Tab]切换排序  [s]换板块  [q]退出 ──────────┘
```

## 为什么做这个

Reddit 是全球最大的讨论社区，但没有好用的终端客户端，更没有中文翻译。这个工具解决两个问题：

- **不用开浏览器** — 全程键盘操作，不打断工作流
- **语言不是障碍** — 标题、正文、评论全部自动翻译，先显示原文再逐条替换，不卡顿

## 安装

```bash
pip install git+https://github.com/osen7/reddit-cli.git
```

启动：

```bash
reddit
```

## 怎么用

启动后进入板块选择页，支持搜索过滤。选中板块后进入帖子列表，回车查看详情和评论。

翻译是后台并发进行的 — 打开页面就能看到内容，翻译完成后自动替换，不需要等待。

## 键位

| 键 | 功能 |
|----|------|
| `↑` `↓` 或 `j` `k` | 上下导航 |
| `Enter` | 进入 / 选择 |
| `Esc` / `Backspace` | 返回上一级 |
| `Tab` | 切换排序（热门 → 最新 → 最高 → 上升） |
| `/` | 在当前板块内搜索 |
| `r` | 刷新 |
| `o` | 用浏览器打开当前帖子 |
| `q` | 退出 |

## 预设板块

启动后直接可选，也可以输入任意板块名搜索。

| 分类 | 板块 |
|------|------|
| 新闻时事 | worldnews, news, politics, geopolitics |
| 科技 | technology, programming, MachineLearning, Python |
| 游戏娱乐 | gaming, funny, movies, music, anime |
| 讨论学习 | AskReddit, todayilearned, explainlikeimfive |
| 中文相关 | China, China_irl, CHNEWS |
| 财经 | wallstreetbets, investing, CryptoCurrency |
| 科学 | science, space, physics, biology |

## 技术细节

- **无需账号** — 使用 Reddit 公开 JSON API，不需要注册或 API Key
- **并发翻译** — 8 个线程同时翻译，列表页标题通常 2-3 秒全部完成
- **Bot 过滤** — 自动过滤机器人和 Moderator 评论
- **评论嵌套** — 显示热门评论及其回复，清理 Markdown 链接格式

依赖：[Textual](https://github.com/Textualize/textual) · [deep-translator](https://github.com/nidhaloff/deep-translator) · [requests](https://github.com/psf/requests) · [click](https://github.com/pallets/click)

## 本地开发

```bash
git clone https://github.com/osen7/reddit-cli.git
cd reddit-cli
pip install -e .
reddit
```

## License

MIT · Co-developed with Claude Sonnet 4.6
