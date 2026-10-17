import time
import webbrowser
import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, Input, TextArea, Button, Select
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual import work

from .api import fetch_posts, fetch_comments, search_posts, format_num, time_ago, post_comment, get_current_user
from .translate import translate
from .subreddits import SUBREDDITS

SORTS = ["hot", "new", "top", "rising"]
SORT_LABELS = {"hot": "热门", "new": "最新", "top": "最高", "rising": "上升"}
SORT_ICONS = {"hot": "🔥", "new": "🕒", "top": "🏆", "rising": "📈"}


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
            yield Input(placeholder="搜索预设板块，或输入任意社区名(如 turkey)回车进入...", id="sub-search")
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
        raw = event.value.strip()
        q = raw.lower()
        if not q:
            self._render_list(self._all_items)
            return
        clean_name = raw.removeprefix("r/").removeprefix("R/").strip()
        filtered = [
            ("sub", name, desc)
            for kind, name, desc in self._all_items
            if kind == "sub" and (q in name.lower() or q in desc.lower() or clean_name.lower() in name.lower())
        ]
        if clean_name and not any(name.lower() == clean_name.lower() for _, name, _ in filtered):
            filtered.insert(0, ("sub", clean_name, "自定义社区 (回车直接进入)"))
        self._render_list(filtered)

    def on_input_submitted(self, event: Input.Submitted):
        raw = event.value.strip()
        clean_name = raw.removeprefix("r/").removeprefix("R/").strip()
        if clean_name:
            self.app.push_screen(PostListScreen(clean_name))

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
        self.orig_title = post_data.get("title", "")
        self.trans_title = ""
        self.showing_translated = True

    def compose(self) -> ComposeResult:
        p = self.post_data
        score = format_num(p["score"])
        comments = format_num(p["num_comments"])
        age = time_ago(p["created_utc"])
        nsfw = " [red][NSFW][/red]" if p.get("over_18") else ""
        yield Label(f"{self.index}. {self._title}{nsfw}", id=f"title-{self.index}", classes="post-title")
        yield Label(f"   ↑{score}  💬{comments}  {age}  {p['subreddit']}", classes="post-meta")

    def update_title(self, translated: str):
        self.trans_title = translated
        if self.showing_translated:
            self._render_title(translated)

    def set_showing_translated(self, show_trans: bool):
        self.showing_translated = show_trans
        text = self.trans_title if (show_trans and self.trans_title) else self.orig_title
        self._render_title(text)

    def _render_title(self, text: str):
        p = self.post_data
        nsfw = " [red][NSFW][/red]" if p.get("over_18") else ""
        self._title = text
        try:
            self.query_one(f"#title-{self.index}", Label).update(f"{self.index}. {text}{nsfw}")
        except Exception:
            pass


class SortTab(Static):
    def __init__(self, key: str, label: str, num: str):
        super().__init__(f"[{num}] {label}", classes="sort-tab", id=f"sort-tab-{key}")
        self.sort_key = key

    def on_click(self) -> None:
        if hasattr(self.screen, "switch_sort"):
            self.screen.switch_sort(self.sort_key)


class LoadMoreItem(ListItem):
    def __init__(self, text: str = "  ▼ 滚动至此或按回车加载更多帖子..."):
        super().__init__(classes="load-more-item")
        self._text = text

    def compose(self) -> ComposeResult:
        yield Label(self._text, id="load-more-label")

    def update_text(self, text: str):
        self._text = text
        try:
            self.query_one("#load-more-label", Label).update(text)
        except Exception:
            pass


class PostListView(ListView):
    def watch_scroll_y(self, old_value, new_value):
        super().watch_scroll_y(old_value, new_value)
        if hasattr(self, "screen") and hasattr(self.screen, "trigger_load_more"):
            if self.max_scroll_y > 0 and new_value >= self.max_scroll_y - 1:
                self.screen.trigger_load_more()


class PostListScreen(Screen):
    BINDINGS = [
        Binding("escape,backspace", "back", "返回"),
        Binding("r", "refresh", "刷新"),
        Binding("c", "comment", "回帖"),
        Binding("tab", "next_sort", "切排序"),
        Binding("t", "toggle_translation", "译/原切换"),
        Binding("1", "sort_hot", "热门", show=False),
        Binding("2", "sort_new", "最新", show=False),
        Binding("3", "sort_top", "最高", show=False),
        Binding("4", "sort_rising", "上升", show=False),
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
        self.after = None
        self.showing_translated = True
        self._is_loading = False
        self._is_loading_more = False
        self.load_more_item = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="sort-bar"):
            yield Label(" 排序模式: ", classes="sort-label")
            yield SortTab("hot", "🔥 热门", "1")
            yield SortTab("new", "🕒 最新", "2")
            yield SortTab("top", "🏆 最高", "3")
            yield SortTab("rising", "📈 上升", "4")
            yield Label("  [dim](快捷键: 1-4 或 Tab 循环)[/dim]", classes="sort-hint")
        yield PostListView(id="post-list")
        yield Footer()

    def on_mount(self):
        self._update_sort_bar()
        self._update_title()
        self.load_posts()

    def _update_sort_bar(self):
        try:
            for key in SORTS:
                tab = self.query_one(f"#sort-tab-{key}", SortTab)
                if key == self.sort and not self._search_query:
                    tab.add_class("-active")
                else:
                    tab.remove_class("-active")
        except Exception:
            pass

    def _update_title(self):
        self.title = f"r/{self.subreddit}"
        label = SORT_LABELS[self.sort]
        self.sub_title = f"{SORT_ICONS.get(self.sort, '')} {label}" + (f" · 搜索: {self._search_query}" if self._search_query else "")

    def action_sort_hot(self):
        self.switch_sort("hot")

    def action_sort_new(self):
        self.switch_sort("new")

    def action_sort_top(self):
        self.switch_sort("top")

    def action_sort_rising(self):
        self.switch_sort("rising")

    def switch_sort(self, new_sort: str):
        if self.sort == new_sort and not self._search_query:
            return
        self.sort = new_sort
        self._search_query = None
        self._update_sort_bar()
        self._update_title()
        self.load_posts()
        self.notify(f"已切换排序: {SORT_ICONS.get(self.sort, '')} {SORT_LABELS[self.sort]}", timeout=1)

    def action_next_sort(self):
        idx = SORTS.index(self.sort)
        next_sort = SORTS[(idx + 1) % len(SORTS)]
        self.switch_sort(next_sort)

    @work(thread=True)
    def load_posts(self):
        self._is_loading = True
        self._is_loading_more = False
        self.after = None
        self.posts = []
        lv = self.query_one("#post-list", ListView)
        self.app.call_from_thread(lv.clear)
        try:
            if self._search_query:
                raw, self.after = search_posts(self._search_query, self.subreddit, limit=20)
            else:
                raw, self.after = fetch_posts(self.subreddit, self.sort, limit=20)
            self.posts = [c["data"] for c in raw if c.get("data")]

            self.load_more_item = LoadMoreItem(
                "  ▼ 滚动至此或按回车加载更多帖子..." if self.after else "  ── 已加载全部帖子 ──"
            )

            def build_original():
                lv.clear()
                for i, p in enumerate(self.posts, 1):
                    item = PostItem(p, i, p.get("title", ""))
                    item.set_showing_translated(self.showing_translated)
                    lv.append(item)
                if self.posts:
                    lv.append(self.load_more_item)
                else:
                    lv.append(ListItem(Label("  [dim]暂无相关帖子[/dim]")))

            self.app.call_from_thread(build_original)

            # 后台逐条翻译替换
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(translate, p.get("title", "")): i for i, p in enumerate(self.posts, 1)}
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
        finally:
            self._is_loading = False

    def trigger_load_more(self):
        if self._is_loading or self._is_loading_more or not self.after:
            return
        self._is_loading_more = True
        self.load_more_posts()

    @work(thread=True)
    def load_more_posts(self):
        lv = self.query_one("#post-list", ListView)
        if self.load_more_item:
            self.app.call_from_thread(self.load_more_item.update_text, "  🔄 正在加载更多帖子并翻译中...")
        try:
            if self._search_query:
                raw, next_after = search_posts(self._search_query, self.subreddit, limit=20, after=self.after)
            else:
                raw, next_after = fetch_posts(self.subreddit, self.sort, limit=20, after=self.after)

            self.after = next_after
            new_posts = [c["data"] for c in raw if c.get("data")]
            if not new_posts:
                self.after = None
                if self.load_more_item:
                    self.app.call_from_thread(self.load_more_item.update_text, "  ── 已加载全部帖子 ──")
                return

            start_idx = len(self.posts) + 1
            self.posts.extend(new_posts)

            new_items = []
            for idx, p in enumerate(new_posts):
                item = PostItem(p, start_idx + idx, p.get("title", ""))
                item.set_showing_translated(self.showing_translated)
                new_items.append(item)

            def mount_new():
                if self.load_more_item and self.load_more_item in lv.children:
                    lv.mount(*new_items, before=self.load_more_item)
                    if self.after:
                        self.load_more_item.update_text("  ▼ 滚动至此或按回车加载更多帖子...")
                    else:
                        self.load_more_item.update_text("  ── 已加载全部帖子 ──")
                else:
                    lv.mount(*new_items)
            self.app.call_from_thread(mount_new)

            # 后台逐条翻译替换新加载的帖子
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(translate, p.get("title", "")): start_idx + idx for idx, p in enumerate(new_posts)}
                for future in as_completed(futures):
                    target_idx = futures[future]
                    try:
                        result = future.result()
                    except Exception:
                        continue

                    def update(idx=target_idx, text=result):
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
            if self.load_more_item:
                self.app.call_from_thread(self.load_more_item.update_text, f"  [red]加载失败: {e} (回车重试)[/red]")
        finally:
            self._is_loading_more = False

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if not event.item:
            return
        lv = self.query_one("#post-list", ListView)
        total = len(lv.children)
        if isinstance(event.item, LoadMoreItem) or (lv.index is not None and lv.index >= total - 3):
            self.trigger_load_more()

    def on_list_view_selected(self, event: ListView.Selected):
        if isinstance(event.item, LoadMoreItem):
            self.trigger_load_more()
            return
        if isinstance(event.item, PostItem):
            self.app.push_screen(PostDetailScreen(event.item.post_data))

    def action_back(self):
        self.app.pop_screen()

    def action_toggle_translation(self):
        self.showing_translated = not self.showing_translated
        lv = self.query_one("#post-list", ListView)
        for item in lv.children:
            if isinstance(item, PostItem):
                item.set_showing_translated(self.showing_translated)
        mode = "中文译文" if self.showing_translated else "原始外文"
        self.notify(f"列表已切换为: {mode}", timeout=1)

    def action_comment(self):
        lv = self.query_one("#post-list", ListView)
        if lv.highlighted_child and isinstance(lv.highlighted_child, PostItem):
            post_data = lv.highlighted_child.post_data
            self.app.push_screen(
                ReplyModalScreen(post_data),
                self._on_list_comment_finished
            )
        else:
            self.notify("请先在列表中选中一条帖子后再按 c 回帖", severity="warning")

    def _on_list_comment_finished(self, result: dict | None):
        if result and result.get("success"):
            self.notify(f"🎉 回帖成功！({result.get('target_id', '')})", timeout=3)

    def action_refresh(self):
        self._search_query = None
        self._update_sort_bar()
        self._update_title()
        self.load_posts()

    def action_search(self):
        self.app.push_screen(SearchScreen(self.subreddit), self._on_search)

    def _on_search(self, query):
        if query:
            self._search_query = query
            self._update_sort_bar()
            self._update_title()
            self.load_posts()

    def action_quit(self):
        self.app.exit()

    def action_cursor_down(self):
        self.query_one("#post-list", ListView).action_cursor_down()

    def action_cursor_up(self):
        self.query_one("#post-list", ListView).action_cursor_up()


def flatten_comments(comments_tree: list) -> list:
    flat = []
    for c in comments_tree:
        flat.append(c)
        if c.get("replies"):
            flat.extend(flatten_comments(c["replies"]))
    return flat


# ─── 回帖弹窗 ───────────────────────────────────────────────────

class ReplyModalScreen(ModalScreen[dict | None]):
    BINDINGS = [
        Binding("ctrl+s,ctrl+j", "submit", "发送", priority=True),
        Binding("escape", "cancel", "取消", priority=True),
    ]

    def __init__(self, post_data: dict, comments_data: list = None, default_target_id: str = None):
        super().__init__()
        self.post_data = post_data
        self.comments_data = comments_data or []
        self.default_target_id = default_target_id
        self._is_submitting = False

    def compose(self) -> ComposeResult:
        post_title = self.post_data.get("title", "")
        post_id = self.post_data.get("id", "")
        post_fullname = self.post_data.get("name") or (f"t3_{post_id}" if post_id else "")

        # 构建可回复的目标选项（扁平化所有层级评论，最多取前60条供挑选）
        options = [(f"💬 回复主贴: {post_title[:32]}...", post_fullname)]
        flat_comments = flatten_comments(self.comments_data)
        for idx, c in enumerate(flat_comments[:60], 1):
            c_author = c.get("author", "匿名")
            c_body = c.get("body_orig", "").strip().replace("\n", " ")[:20]
            c_id = c.get("name") or (f"t1_{c.get('id')}" if c.get("id") else "")
            depth = c.get("depth", 0)
            prefix = "↳ " if depth == 0 else ("  ↳ " if depth == 1 else "    ↳ ")
            if c_id:
                options.append((f"{prefix}#{idx} 回复 u/{c_author}: {c_body}...", c_id))

        initial_val = self.default_target_id if (self.default_target_id and any(val == self.default_target_id for _, val in options)) else post_fullname

        with Vertical(id="reply-dialog"):
            yield Label("💬 Reddit 回帖 / 发表评论", id="reply-dialog-title")
            if len(options) > 1:
                yield Label("回复目标:", classes="reply-sublabel")
                yield Select(options, value=initial_val, allow_blank=False, id="reply-target-select")
            else:
                yield Label(f"回复主贴: {post_title[:45]}...", id="reply-target-label")
            yield Label("正在检测当前登录账号...", id="reply-auth-info")
            yield TextArea(placeholder="在此输入你的回复内容 (支持 Markdown 语法，Ctrl+S 发送)...", id="reply-text-area")
            yield Label("", id="reply-status-label")
            with Horizontal(id="reply-buttons"):
                yield Button("发送评论 (Ctrl+S)", variant="primary", id="btn-submit")
                yield Button("取消 (Esc)", variant="default", id="btn-cancel")

    def on_mount(self):
        self.query_one("#reply-text-area", TextArea).focus()
        self._check_auth_info()

    @work(thread=True)
    def _check_auth_info(self):
        user = get_current_user()
        def update_ui():
            try:
                label = self.query_one("#reply-auth-info", Label)
                if user:
                    label.update(f"👤 当前账号: [green]{user}[/green]")
                else:
                    label.update("[yellow]⚠️ 未检测到已登录账号 (回帖需要凭证，建议终端运行 opencli reddit login)[/yellow]")
            except Exception:
                pass
        self.app.call_from_thread(update_ui)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-submit":
            self.action_submit()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_cancel(self):
        if not self._is_submitting:
            self.dismiss(None)

    def action_submit(self):
        if self._is_submitting:
            return
        text = self.query_one("#reply-text-area", TextArea).text.strip()
        status_label = self.query_one("#reply-status-label", Label)
        if not text:
            status_label.update("[red]评论内容不能为空！[/red]")
            return

        target_id = None
        if self.query("#reply-target-select"):
            sel = self.query_one("#reply-target-select", Select)
            target_id = sel.value
        if not target_id or target_id == Select.NULL:
            target_id = self.post_data.get("name") or f"t3_{self.post_data.get('id', '')}"

        self._is_submitting = True
        submit_btn = self.query_one("#btn-submit", Button)
        submit_btn.disabled = True
        status_label.update("[yellow]⏳ 正在发送回帖至 Reddit，请稍候...[/yellow]")
        self._do_post(target_id, text)

    @work(thread=True)
    def _do_post(self, target_id: str, text: str):
        try:
            res = post_comment(target_id, text)
            def on_success():
                try:
                    self.query_one("#reply-status-label", Label).update("[green]✓ 回帖发表成功！[/green]")
                except Exception:
                    pass
            self.app.call_from_thread(on_success)
            time.sleep(0.6)
            self.app.call_from_thread(self.dismiss, {
                "success": True,
                "target_id": target_id,
                "text": text,
                "author": res.get("author") or "你",
                "message": res.get("message", "回帖成功"),
            })
        except Exception as e:
            def on_fail():
                self._is_submitting = False
                try:
                    self.query_one("#btn-submit", Button).disabled = False
                    self.query_one("#reply-status-label", Label).update(f"[red]❌ 发送失败: {e}[/red]")
                except Exception:
                    pass
            self.app.call_from_thread(on_fail)


# ─── 第三级：帖子详情 ────────────────────────────────────────────

COMMENT_SORTS = ["confidence", "top", "new", "controversial"]
COMMENT_SORT_LABELS = {
    "confidence": "🔥 最佳 (Best)",
    "top": "🏆 最高 (Top)",
    "new": "🕒 最新 (New)",
    "controversial": "⚡ 争议 (Controversial)",
}
COMMENT_SORT_ICONS = {
    "confidence": "🔥最佳",
    "top": "🏆最高",
    "new": "🕒最新",
    "controversial": "⚡争议",
}


class PostDetailScreen(Screen):
    BINDINGS = [
        Binding("escape,backspace", "back", "返回"),
        Binding("c", "comment", "回帖"),
        Binding("m", "load_more_comments", "加更多评论"),
        Binding("a", "load_all_comments", "加全部评论"),
        Binding("s", "toggle_comment_sort", "切评论排序"),
        Binding("t", "toggle_translation", "译/原切换"),
        Binding("r", "refresh_comments", "刷新评论"),
        Binding("o", "open_browser", "浏览器"),
        Binding("q", "quit", "退出"),
        Binding("j", "scroll_down", show=False),
        Binding("k", "scroll_up", show=False),
    ]

    def __init__(self, post_data: dict):
        super().__init__()
        self.post_data = post_data
        self.showing_translated = True
        self.title_orig = post_data.get("title", "")
        self.title_trans = ""
        self.body_orig = html_lib.unescape(post_data.get("selftext", "").strip())
        self.body_trans = ""
        self.comments_data = []
        self.comments_limit = 500
        self.comments_sort = "confidence"
        self.total_comments_count = post_data.get("num_comments", 0)
        self._is_loading_more_comments = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id="detail-scroll")
        yield Footer()

    def on_mount(self):
        p = self.post_data
        self.title = f"{p.get('subreddit', '')}"
        self.sub_title = "加载中..."
        self.load_detail()

    def _update_subtitle(self):
        p = self.post_data
        score = format_num(p.get("score", 0))
        sort_icon = COMMENT_SORT_ICONS.get(self.comments_sort, "")
        loaded_count = len(flatten_comments(self.comments_data))
        self.sub_title = (
            f"↑{score} · 💬{loaded_count}/{self.total_comments_count}条 ({sort_icon}) · "
            f"[s]切排序 [r]刷新 [c]回帖 [t]切换原文/译文"
        )

    def action_toggle_translation(self):
        self.showing_translated = not self.showing_translated
        self._apply_display_mode()
        mode = "中文译文" if self.showing_translated else "原始外文"
        self.notify(f"已切换为: {mode}", timeout=1)

    def _apply_display_mode(self):
        try:
            t = self.title_trans if (self.showing_translated and self.title_trans) else self.title_orig
            self.query_one("#detail-title", Static).update(t)
        except Exception:
            pass

        if self.body_orig:
            try:
                b = self.body_trans if (self.showing_translated and self.body_trans) else self.body_orig
                self.query_one("#detail-body", Static).update(b)
            except Exception:
                pass

        self._render_comments_list()

    def _render_comments_list(self):
        sort_lbl = COMMENT_SORT_LABELS.get(self.comments_sort, "")
        sort_icon = COMMENT_SORT_ICONS.get(self.comments_sort, "")
        flat_list = flatten_comments(self.comments_data)
        loaded_count = len(flat_list)
        self._update_subtitle()
        try:
            scroll = self.query_one("#detail-scroll")
            scroll.query_one("#comments-header", Static).update(
                f"💬 评论区 (已加载 {loaded_count}/{self.total_comments_count} 条) · 当前排序: {sort_lbl}"
            )
        except Exception:
            pass

        try:
            container = self.query_one("#comments-container", Vertical)
            container.remove_children()
            if not self.comments_data:
                container.mount(Static("暂无评论", classes="no-comments"))
                return

            widgets = []
            for i, c in enumerate(flat_list, 1):
                depth = c.get("depth", 0)
                indent_spaces = "  " * depth
                if depth == 0:
                    prefix = "┌"
                    meta_cls = "comment-meta"
                    body_cls = "comment-body"
                elif depth == 1:
                    prefix = "╰"
                    meta_cls = "reply-meta"
                    body_cls = "reply-body"
                else:
                    prefix = "↳"
                    meta_cls = "sub-reply-meta"
                    body_cls = "sub-reply-body"

                c_id = c.get("id", str(i))
                widgets.append(Static(
                    f"{indent_spaces}{prefix} u/{c['author']} · ↑{format_num(c['score'])}",
                    classes=meta_cls
                ))
                body_show = c.get("body_trans") if (self.showing_translated and c.get("body_trans")) else c.get("body_orig", "")
                widgets.append(Static(
                    f"{indent_spaces}{body_show}",
                    classes=body_cls,
                    id=f"cnode-{c_id}"
                ))
                if depth == 0 and i > 1:
                    widgets.insert(-2, Static("", classes="spacer"))

            if loaded_count < self.total_comments_count:
                hint_text = (
                    f"── 当前已加载 {loaded_count} 条 / 全帖共 {self.total_comments_count} 条 ──\n"
                    f"[dim]快捷操作: 按 [bold yellow]s[/bold yellow] 切换排序 ({sort_icon})  |  按 [bold cyan]r[/bold cyan] 刷新  |  按 [bold magenta]c[/bold magenta] 回帖  |  按 [bold blue]t[/bold blue] 切换译文/原文[/dim]"
                )
            else:
                hint_text = (
                    f"── 已加载全帖评论 (共 {loaded_count} 条) ──\n"
                    f"[dim]快捷操作: 按 [bold yellow]s[/bold yellow] 切换排序 ({sort_icon})  |  按 [bold cyan]r[/bold cyan] 刷新  |  按 [bold magenta]c[/bold magenta] 回帖  |  按 [bold blue]t[/bold blue] 切换译文/原文[/dim]"
                )
            widgets.append(Static(hint_text, classes="comments-load-hint", id="comments-load-hint"))

            container.mount(*widgets)
        except Exception:
            pass

    @work(thread=True)
    def load_detail(self):
        p = self.post_data
        selftext = self.body_orig
        author = p.get("author", "[deleted]")
        score = format_num(p.get("score", 0))
        num_comments = format_num(p.get("num_comments", 0))
        age = time_ago(p.get("created_utc", 0))
        subreddit = p.get("subreddit", "")
        title_en = self.title_orig

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
            scroll.mount(Vertical(id="comments-container"))
            self._update_subtitle()

        self.app.call_from_thread(show_skeleton)

        # 第二步：翻译标题和正文
        title_zh = translate(title_en)
        self.title_trans = title_zh

        def update_title():
            if self.showing_translated:
                try:
                    self.query_one("#detail-title", Static).update(title_zh)
                except Exception:
                    pass

        self.app.call_from_thread(update_title)

        if selftext:
            body_zh = translate(selftext[:2000])
            self.body_trans = body_zh

            def update_body():
                if self.showing_translated:
                    try:
                        self.query_one("#detail-body", Static).update(body_zh)
                    except Exception:
                        pass

            self.app.call_from_thread(update_body)

        # 第三步：加载首批热门评论并开启并发翻译
        self.reload_comments_data()

    @work(thread=True)
    def reload_comments_data(self):
        self._is_loading_more_comments = True
        try:
            permalink = self.post_data.get("permalink", "")
            _, new_comments_data = fetch_comments(
                permalink,
                limit=self.comments_limit,
                depth=10,
                sort=self.comments_sort
            )

            # 保留已有翻译，避免重复网络翻译
            trans_cache = {}
            for old_c in flatten_comments(self.comments_data):
                if old_c.get("body_trans"):
                    trans_cache[old_c["body_orig"]] = old_c["body_trans"]

            flat_new = flatten_comments(new_comments_data)
            for node in flat_new:
                clean_b = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', node["body"])
                node["body_orig"] = clean_b
                node["body_trans"] = trans_cache.get(clean_b, "")

            self.comments_data = new_comments_data

            # 先立即渲染（带原文或已有翻译）
            self.app.call_from_thread(self._render_comments_list)

            # 后台并发补齐未翻译的评论
            untranslated = [
                (c["id"], c["body_orig"], "  " * c.get("depth", 0))
                for c in flat_new
                if not c.get("body_trans")
            ]
            if untranslated:
                def translate_item(args):
                    cid, body, indent = args
                    return cid, translate(body), indent

                with ThreadPoolExecutor(max_workers=8) as ex:
                    futures = {ex.submit(translate_item, task): task[0] for task in untranslated}
                    for future in as_completed(futures):
                        cid = futures[future]
                        try:
                            _, translated, indent = future.result()
                            for n in flat_new:
                                if n["id"] == cid:
                                    n["body_trans"] = translated
                                    break
                        except Exception:
                            continue

                        def update_comment(dom_id=f"cnode-{cid}", text=translated, ind=indent):
                            if self.showing_translated:
                                try:
                                    self.query_one(f"#{dom_id}", Static).update(f"{ind}{text}")
                                except Exception:
                                    pass
                        self.app.call_from_thread(update_comment)

        except Exception as e:
            self.app.call_from_thread(self.notify, f"评论加载异常: {e}", severity="error")
        finally:
            self._is_loading_more_comments = False

    def action_load_more_comments(self):
        if self._is_loading_more_comments:
            self.notify("正在加载评论中，请稍候...", severity="warning")
            return
        if self.comments_limit >= 1500:
            self.notify("已达单次加载最大上限 (1500 条)", severity="information")
            return
        self.comments_limit += 500
        self.notify(f"正在加载更多评论 (上限: {self.comments_limit}条)...", timeout=2)
        self.reload_comments_data()

    def action_load_all_comments(self):
        if self._is_loading_more_comments:
            self.notify("正在加载评论中，请稍候...", severity="warning")
            return
        self.comments_limit = 1000
        self.notify(f"正在一键加载全帖评论 (全帖共 {self.total_comments_count} 条)...", timeout=2)
        self.reload_comments_data()

    def action_toggle_comment_sort(self):
        if self._is_loading_more_comments:
            self.notify("正在加载评论中，请稍候...", severity="warning")
            return
        idx = COMMENT_SORTS.index(self.comments_sort)
        self.comments_sort = COMMENT_SORTS[(idx + 1) % len(COMMENT_SORTS)]
        label = COMMENT_SORT_LABELS[self.comments_sort]
        self.notify(f"评论排序已切换为: {label}", timeout=2)
        self.reload_comments_data()

    def action_refresh_comments(self):
        if self._is_loading_more_comments:
            self.notify("正在加载评论中，请稍候...", severity="warning")
            return
        self.notify("正在刷新当前评论...", timeout=1)
        self.reload_comments_data()

    def action_back(self):
        self.app.pop_screen()

    def action_comment(self):
        self.app.push_screen(
            ReplyModalScreen(self.post_data, self.comments_data),
            self._on_comment_finished
        )

    def _on_comment_finished(self, result: dict | None):
        if not result or not result.get("success"):
            return
        text = result.get("text", "")
        author = result.get("author") or "你"
        target_id = result.get("target_id", "")
        self.notify(f"🎉 回帖成功！", timeout=3)

        new_c = {
            "id": f"new_{int(time.time())}",
            "name": "",
            "author": author,
            "score": 1,
            "body": text,
            "body_orig": text,
            "body_trans": text,
            "depth": 0,
            "replies": [],
        }

        if target_id.startswith("t1_"):
            target_placed = False
            for c in flatten_comments(self.comments_data):
                if c.get("name") == target_id or f"t1_{c.get('id')}" == target_id:
                    new_c["depth"] = c.get("depth", 0) + 1
                    c.setdefault("replies", []).insert(0, new_c)
                    target_placed = True
                    break
            if not target_placed:
                self.comments_data.insert(0, new_c)
        else:
            self.comments_data.insert(0, new_c)

        self._render_comments_list()

        self.total_comments_count += 1
        self._render_comments_list()

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
    .sub-reply-meta { color: $text-disabled; }
    .sub-reply-body { text-wrap: wrap; color: $text-muted; padding-left: 2; }
    .no-comments { color: $text-muted; }
    .spacer { height: 1; }

    #search-container {
        margin: 4 8;
        height: auto;
    }

    #sub-search { margin-bottom: 1; }

    #sort-bar {
        height: 3;
        background: $surface-darken-1;
        border-bottom: solid $surface-lighten-1;
        align: left middle;
        padding: 0 1;
    }

    .sort-label {
        color: $accent;
        text-style: bold;
        padding: 0 1;
    }

    .sort-tab {
        padding: 0 1;
        margin: 0 1;
        color: $text-muted;
    }

    .sort-tab:hover {
        background: $surface-lighten-1;
        color: $text;
    }

    .sort-tab.-active {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    .sort-hint {
        color: $text-muted;
        padding: 0 1;
    }

    .load-more-item {
        padding: 1 1;
        border-top: dashed $surface-lighten-2;
    }

    ReplyModalScreen {
        align: center middle;
    }

    #reply-dialog {
        width: 78;
        max-width: 90%;
        height: auto;
        max-height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #reply-dialog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #reply-target-label {
        color: $text-muted;
        margin-bottom: 1;
    }

    .reply-sublabel {
        color: $text-muted;
    }

    #reply-target-select {
        margin-bottom: 1;
    }

    #reply-auth-info {
        margin-bottom: 1;
    }

    #reply-text-area {
        height: 8;
        margin-bottom: 1;
        border: solid $primary-darken-1;
    }

    #reply-status-label {
        height: 1;
        margin-bottom: 1;
    }

    #reply-buttons {
        align: right middle;
        height: auto;
    }

    #reply-buttons Button {
        margin-left: 1;
    }

    .comments-load-hint {
        padding: 1 1;
        margin-top: 1;
        border-top: dashed $surface-lighten-2;
        color: $text-muted;
    }
    """

    def __init__(self, initial_subreddit: str = None, **kwargs):
        super().__init__(**kwargs)
        self.initial_subreddit = initial_subreddit

    def on_mount(self):
        self.push_screen(SubredditScreen())
        if self.initial_subreddit:
            sub = self.initial_subreddit.strip().removeprefix("r/").removeprefix("R/")
            if sub:
                self.push_screen(PostListScreen(sub))
