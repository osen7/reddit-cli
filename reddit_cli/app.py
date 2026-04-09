import webbrowser
import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, Input
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.binding import Binding
from textual import work

from .api import fetch_posts, fetch_comments, search_posts, format_num, time_ago
from .translate import translate
from .subreddits import SUBREDDITS

SORTS = ["hot", "new", "top", "rising"]
SORT_LABELS = {"hot": "热门", "new": "最新", "top": "最高", "rising": "上升"}


# ─── 第一级：板块选择 ────────────────────────────────────────────

class SubredditItem(ListItem):
    def __init__(self, name: str, desc: str):
        super().__init__()
        self.sub_name = name
        self.sub_desc = desc

    def compose(self) -> ComposeResult:
        yield Label(f"{self.sub_name}  [dim]{self.sub_desc}[/dim]")


class CategoryItem(ListItem):
    def __init__(self, label: str):
        super().__init__(disabled=True)
        self._label = label

    def compose(self) -> ComposeResult:
        yield Label(f"\n{self._label}", classes="category-label")


class SubredditScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="搜索板块...", id="sub-search")
            yield ListView(id="sub-list")
        yield Footer()

    def on_mount(self):
        self.title = "Reddit CLI"
        self.sub_title = "选择板块"
        self._all_items = []
        for group in SUBREDDITS:
            self._all_items.append(("category", group["category"], ""))
            for name, desc in group["subs"]:
                self._all_items.append(("sub", name, desc))
        self._render_list(self._all_items)
        # 聚焦到列表
        self.query_one("#sub-list").focus()

    def _render_list(self, items):
        lv = self.query_one("#sub-list", ListView)
        lv.clear()
        for kind, name, desc in items:
            if kind == "category":
                lv.append(CategoryItem(name))
            else:
                lv.append(SubredditItem(name, desc))

    def on_input_changed(self, event: Input.Changed):
        q = event.value.strip().lower()
        if not q:
            self._render_list(self._all_items)
            return
        filtered = [
            ("sub", name, desc)
            for kind, name, desc in self._all_items
            if kind == "sub" and (q in name.lower() or q in desc.lower())
        ]
        self._render_list(filtered)

    def on_list_view_selected(self, event: ListView.Selected):
        if isinstance(event.item, SubredditItem):
            self.app.push_screen(PostListScreen(event.item.sub_name))

    def action_quit(self):
        self.app.exit()


# ─── 第二级：帖子列表 ────────────────────────────────────────────

class PostItem(ListItem):
    def __init__(self, post_data: dict, index: int, title: str):
        super().__init__()
        self.post_data = post_data
        self.index = index
        self._title = title

    def compose(self) -> ComposeResult:
        p = self.post_data
        score = format_num(p["score"])
        comments = format_num(p["num_comments"])
        age = time_ago(p["created_utc"])
        nsfw = " [red][NSFW][/red]" if p.get("over_18") else ""
        yield Label(f"{self.index}. {self._title}{nsfw}", id=f"title-{self.index}", classes="post-title")
        yield Label(f"   ↑{score}  💬{comments}  {age}  {p['subreddit']}", classes="post-meta")

    def update_title(self, translated: str):
        p = self.post_data
        nsfw = " [red][NSFW][/red]" if p.get("over_18") else ""
        self._title = translated
        try:
            self.query_one(f"#title-{self.index}", Label).update(f"{self.index}. {translated}{nsfw}")
        except Exception:
            pass


class PostListScreen(Screen):
    BINDINGS = [
        Binding("escape,backspace", "back", "返回"),
        Binding("r", "refresh", "刷新"),
        Binding("tab", "next_sort", "切换排序"),
        Binding("slash", "search", "搜索"),
        Binding("q", "quit", "退出"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def __init__(self, subreddit: str, sort: str = "hot"):
        super().__init__()
        self.subreddit = subreddit
        self.sort = sort
        self.posts = []
        self._search_query = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(id="post-list")
        yield Footer()

    def on_mount(self):
        self._update_title()
        self.load_posts()

    def _update_title(self):
        self.title = f"{self.subreddit}"
        label = SORT_LABELS[self.sort]
        self.sub_title = f"{label}" + (f" · 搜索: {self._search_query}" if self._search_query else "")

    @work(thread=True)
    def load_posts(self):
        lv = self.query_one("#post-list", ListView)
        self.app.call_from_thread(lv.clear)
        try:
            if self._search_query:
                raw = search_posts(self._search_query, self.subreddit)
            else:
                raw = fetch_posts(self.subreddit, self.sort)
            self.posts = [c["data"] for c in raw]

            # 立刻显示原文
            def build_original():
                lv.clear()
                for i, p in enumerate(self.posts, 1):
                    lv.append(PostItem(p, i, p["title"]))

            self.app.call_from_thread(build_original)

            # 后台逐条翻译替换
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(translate, p["title"]): i for i, p in enumerate(self.posts, 1)}
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        result = future.result()
                    except Exception:
                        continue

                    def update(idx=i, text=result):
                        try:
                            items = [w for w in lv.children if isinstance(w, PostItem)]
                            for item in items:
                                if item.index == idx:
                                    item.update_title(text)
                                    break
                        except Exception:
                            pass

                    self.app.call_from_thread(update)

        except Exception as e:
            def show_err():
                lv.clear()
                lv.append(ListItem(Label(f"[red]加载失败: {e}[/red]")))
            self.app.call_from_thread(show_err)

    def on_list_view_selected(self, event: ListView.Selected):
        if isinstance(event.item, PostItem):
            self.app.push_screen(PostDetailScreen(event.item.post_data))

    def action_back(self):
        self.app.pop_screen()

    def action_refresh(self):
        self._search_query = None
        self._update_title()
        self.load_posts()

    def action_next_sort(self):
        idx = SORTS.index(self.sort)
        self.sort = SORTS[(idx + 1) % len(SORTS)]
        self._search_query = None
        self._update_title()
        self.load_posts()
        self.notify(f"切换到{SORT_LABELS[self.sort]}", timeout=1)

    def action_search(self):
        self.app.push_screen(SearchScreen(self.subreddit), self._on_search)

    def _on_search(self, query):
        if query:
            self._search_query = query
            self._update_title()
            self.load_posts()

    def action_quit(self):
        self.app.exit()

    def action_cursor_down(self):
        self.query_one("#post-list", ListView).action_cursor_down()

    def action_cursor_up(self):
        self.query_one("#post-list", ListView).action_cursor_up()


# ─── 第三级：帖子详情 ────────────────────────────────────────────

class PostDetailScreen(Screen):
    BINDINGS = [
        Binding("escape,backspace", "back", "返回"),
        Binding("o", "open_browser", "浏览器"),
        Binding("q", "quit", "退出"),
        Binding("j", "scroll_down", show=False),
        Binding("k", "scroll_up", show=False),
    ]

    def __init__(self, post_data: dict):
        super().__init__()
        self.post_data = post_data

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id="detail-scroll")
        yield Footer()

    def on_mount(self):
        p = self.post_data
        self.title = f"{p.get('subreddit', '')}"
        self.sub_title = "加载中..."
        self.load_detail()

    @work(thread=True)
    def load_detail(self):
        p = self.post_data
        permalink = p.get("permalink", "")
        selftext = html_lib.unescape(p.get("selftext", "").strip())
        author = p.get("author", "[deleted]")
        score = format_num(p.get("score", 0))
        num_comments = format_num(p.get("num_comments", 0))
        age = time_ago(p.get("created_utc", 0))
        subreddit = p.get("subreddit", "")
        title_en = p.get("title", "")

        # 第一步：立刻显示原文标题和帖子信息
        def show_skeleton():
            scroll = self.query_one("#detail-scroll")
            scroll.remove_children()
            scroll.mount(Static(title_en, classes="detail-title", id="detail-title"))
            scroll.mount(Static(
                f"u/{author} · {subreddit} · {age} · ↑{score} · 💬{num_comments}",
                classes="detail-meta"
            ))
            if selftext:
                scroll.mount(Static("─" * 60, classes="divider"))
                scroll.mount(Static(selftext[:2000], classes="detail-body", id="detail-body"))
            scroll.mount(Static("─" * 60, classes="divider"))
            scroll.mount(Static("💬 加载评论中...", classes="section-header", id="comments-header"))
            self.sub_title = f"↑{score} · 💬{num_comments}条评论"

        self.app.call_from_thread(show_skeleton)

        # 第二步：翻译标题和正文
        title_zh = translate(title_en)

        def update_title():
            try:
                self.query_one("#detail-title", Static).update(title_zh)
            except Exception:
                pass

        self.app.call_from_thread(update_title)

        if selftext:
            body_zh = translate(selftext[:2000])

            def update_body():
                try:
                    self.query_one("#detail-body", Static).update(body_zh)
                except Exception:
                    pass

            self.app.call_from_thread(update_body)

        # 第三步：加载评论
        try:
            _, comments = fetch_comments(permalink)
            # 过滤 bot 和空评论
            unique, seen = [], set()
            for c in comments:
                author_name = c["author"].lower()
                body = c["body"].strip()
                if not body or body == "[deleted]" or body == "[removed]":
                    continue
                if "bot" in author_name or "moderator" in author_name.lower():
                    continue
                key = (c["author"], body[:50])
                if key in seen:
                    continue
                seen.add(key)
                # 清理 Markdown 链接 [text](url) -> text
                c["body"] = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', body)
                unique.append(c)
        except Exception:
            unique = []

        # 第四步：先显示原文评论
        def show_comments_original():
            scroll = self.query_one("#detail-scroll")
            try:
                scroll.query_one("#comments-header", Static).update(f"💬 热门评论 ({len(unique)})")
            except Exception:
                pass
            if not unique:
                scroll.mount(Static("暂无评论", classes="no-comments"))
                return
            for i, c in enumerate(unique, 1):
                scroll.mount(Static(
                    f"┌ u/{c['author']} · ↑{format_num(c['score'])}",
                    classes="comment-meta"
                ))
                scroll.mount(Static(c["body"], classes="comment-body", id=f"comment-{i}"))
                for j, reply in enumerate(c.get("replies", []), 1):
                    scroll.mount(Static(
                        f"  ╰ u/{reply['author']} · ↑{format_num(reply['score'])}",
                        classes="reply-meta"
                    ))
                    scroll.mount(Static(reply["body"], classes="reply-body", id=f"reply-{i}-{j}"))
                if i < len(unique):
                    scroll.mount(Static("", classes="spacer"))

        self.app.call_from_thread(show_comments_original)

        # 第五步：并发翻译评论，逐条替换
        def translate_comment(args):
            i, body = args
            return i, translate(body)

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(translate_comment, (i, c["body"])): i for i, c in enumerate(unique, 1)}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    _, translated = future.result()
                except Exception:
                    continue

                def update_comment(idx=i, text=translated):
                    try:
                        self.query_one(f"#comment-{idx}", Static).update(text)
                    except Exception:
                        pass

                self.app.call_from_thread(update_comment)

        # 翻译回复
        reply_tasks = []
        for i, c in enumerate(unique, 1):
            for j, reply in enumerate(c.get("replies", []), 1):
                reply_tasks.append((i, j, reply["body"]))

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(translate, body): (i, j) for i, j, body in reply_tasks}
            for future in as_completed(futures):
                i, j = futures[future]
                try:
                    text = future.result()
                except Exception:
                    continue

                def update_reply(ri=i, rj=j, text=text):
                    try:
                        self.query_one(f"#reply-{ri}-{rj}", Static).update(text)
                    except Exception:
                        pass

                self.app.call_from_thread(update_reply)

    def action_back(self):
        self.app.pop_screen()

    def action_open_browser(self):
        url = f"https://www.reddit.com{self.post_data.get('permalink', '')}"
        webbrowser.open(url)

    def action_quit(self):
        self.app.exit()

    def action_scroll_down(self):
        self.query_one("#detail-scroll").scroll_down()

    def action_scroll_up(self):
        self.query_one("#detail-scroll").scroll_up()


# ─── 搜索页 ──────────────────────────────────────────────────────

class SearchScreen(Screen):
    BINDINGS = [Binding("escape", "dismiss", "取消")]

    def __init__(self, subreddit: str):
        super().__init__()
        self.subreddit = subreddit

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="search-container"):
            yield Label(f"在 {self.subreddit} 中搜索", classes="section-header")
            yield Input(placeholder="输入关键词，回车确认...", id="search-input")
        yield Footer()

    def on_mount(self):
        self.title = "搜索"
        self.query_one("#search-input").focus()

    def on_input_submitted(self, event: Input.Submitted):
        self.dismiss(event.value.strip())


# ─── App 入口 ─────────────────────────────────────────────────────

class RedditApp(App):
    CSS = """
    Screen { background: $surface; }

    .category-label {
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }

    SubredditItem { padding: 0 1; border-bottom: solid $surface-darken-1; }
    SubredditItem:hover { background: $surface-lighten-1; }
    SubredditItem.-highlighted { background: $primary-darken-2; }

    PostItem { padding: 0 1; border-bottom: solid $surface-darken-1; }
    PostItem:hover { background: $surface-lighten-1; }
    PostItem.-highlighted { background: $primary-darken-2; }

    .post-title { color: $text; text-wrap: wrap; }
    .post-meta { color: $text-muted; }

    #detail-scroll { padding: 1 2; }
    .detail-title { text-style: bold; color: $text; text-wrap: wrap; margin-bottom: 1; }
    .detail-meta { color: $text-muted; margin-bottom: 1; }
    .detail-body { text-wrap: wrap; margin-bottom: 1; }
    .divider { color: $surface-lighten-2; margin: 1 0; }
    .section-header { text-style: bold; color: $accent; margin-bottom: 1; }
    .comment-meta { color: $text-muted; text-style: bold; }
    .comment-body { text-wrap: wrap; margin-bottom: 0; padding-left: 1; }
    .reply-meta { color: $text-disabled; }
    .reply-body { text-wrap: wrap; color: $text-muted; padding-left: 2; }
    .no-comments { color: $text-muted; }
    .spacer { height: 1; }

    #search-container {
        margin: 4 8;
        height: auto;
    }

    #sub-search { margin-bottom: 1; }
    """

    def on_mount(self):
        self.push_screen(SubredditScreen())
