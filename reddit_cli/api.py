import os
import json
import shutil
import subprocess
import requests
import time
import html
import re
from .translate import get_system_proxies

_session = requests.Session()
_proxies = get_system_proxies()
if _proxies:
    _session.proxies.update(_proxies)

_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
})
_session_initialized = False


def reload_proxies():
    global _proxies
    _proxies = get_system_proxies()
    _session.proxies.clear()
    if _proxies:
        _session.proxies.update(_proxies)


def _init_session():
    global _session_initialized
    reload_proxies()
    try:
        resp = _session.get("https://www.reddit.com", timeout=8)
        html_text = resp.text
        match_sol = re.search(r'\(async e=>e\+e\)\(\"([^\"]+)\"\)', html_text)
        match_token = re.search(r'name=\"jsc_token\"\s+value=\"([^\"]+)\"', html_text)
        if match_sol and match_token:
            seed = match_sol.group(1)
            token = match_token.group(1)
            challenge_url = f"https://www.reddit.com/?solution={seed + seed}&js_challenge=1&jsc_token={token}&jsc_orig_r="
            _session.get(challenge_url, timeout=8)
        _session_initialized = True
    except Exception:
        pass


def _get(url, timeout=10):
    global _session_initialized
    if not _session_initialized:
        _init_session()
    try:
        r = _session.get(url, timeout=timeout)
        if r.status_code == 403:
            _init_session()
            r = _session.get(url, timeout=timeout)
        r.raise_for_status()
        return r
    except requests.exceptions.ProxyError as e:
        reload_proxies()
        proxy_info = _session.proxies.get("https") or _session.proxies.get("http") or "本地代理"
        raise ConnectionError(
            f"代理连接失败 ({proxy_info}): 代理节点无法连通 Reddit (Tunnel 503/Timeout)。请在 Shadowrocket 中切换可用节点后按 r 刷新"
        ) from e
    except requests.exceptions.Timeout as e:
        reload_proxies()
        raise ConnectionError(
            "网络请求超时: 当前代理节点延迟过高或丢包，请在代理软件中切换节点后按 r 刷新"
        ) from e


def fetch_posts(subreddit, sort="hot", limit=20, after=None):
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    if after:
        url += f"&after={after}"
    r = _get(url, timeout=10)
    data = r.json().get("data", {})
    return data.get("children", []), data.get("after")


def fetch_comments(permalink, limit=500, depth=10, sort="confidence"):
    url = f"https://www.reddit.com{permalink}.json?limit={limit}&depth={depth}&sort={sort}"
    r = _get(url, timeout=15)
    data = r.json()
    post = data[0]["data"]["children"][0]["data"]
    comments_raw = data[1]["data"]["children"]
    comments = []
    for c in comments_raw:
        node = _extract_comment_node(c, depth=0, max_depth=10)
        if node:
            comments.append(node)
    return post, comments


def _extract_comment_node(item, depth=0, max_depth=10):
    if not item or not isinstance(item, dict) or item.get("kind") != "t1":
        return None
    d = item.get("data", {})
    body = html.unescape(d.get("body", "")).strip()
    if not body or body in ["[deleted]", "[removed]"]:
        return None
    author = d.get("author", "[deleted]")
    if "automoderator" in author.lower():
        return None

    node = {
        "id": d.get("id", ""),
        "name": d.get("name", "") or (f"t1_{d.get('id')}" if d.get("id") else ""),
        "author": author,
        "body": body,
        "score": d.get("score", 0),
        "depth": depth,
        "replies": [],
    }

    if depth < max_depth:
        replies_obj = d.get("replies")
        if isinstance(replies_obj, dict):
            for child in replies_obj.get("data", {}).get("children", []):
                child_node = _extract_comment_node(child, depth=depth + 1, max_depth=max_depth)
                if child_node:
                    node["replies"].append(child_node)

    return node


def _extract_replies(replies, max_replies=50):
    if not replies or not isinstance(replies, dict):
        return []
    children = replies.get("data", {}).get("children", [])
    result = []
    for c in children:
        node = _extract_comment_node(c, depth=1)
        if node:
            result.append(node)
    return result[:max_replies]


def search_posts(query, subreddit=None, limit=20, after=None):
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=1&limit={limit}"
    else:
        url = f"https://www.reddit.com/search.json?q={query}&limit={limit}"
    if after:
        url += f"&after={after}"
    r = _get(url, timeout=10)
    data = r.json().get("data", {})
    return data.get("children", []), data.get("after")


def search_subreddits(query, limit=10):
    url = f"https://www.reddit.com/subreddits/search.json?q={query}&limit={limit}"
    r = _get(url, timeout=10)
    return r.json()["data"]["children"]


def format_num(n):
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def time_ago(ts):
    diff = int(time.time() - ts)
    if diff < 60:
        return f"{diff}s"
    elif diff < 3600:
        return f"{diff//60}m"
    elif diff < 86400:
        return f"{diff//3600}h"
    else:
        return f"{diff//86400}d"


# ─── 回帖与认证支持 ───────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.config/reddit-cli")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
_cached_user = None


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_reddit_cookie() -> str | None:
    cookie = os.environ.get("REDDIT_SESSION") or os.environ.get("REDDIT_COOKIE")
    if cookie:
        return cookie.strip()
    cfg = load_config()
    return cfg.get("reddit_session")


def set_reddit_cookie(cookie: str):
    cfg = load_config()
    cfg["reddit_session"] = cookie.strip()
    save_config(cfg)


def get_current_user(force_refresh: bool = False) -> str | None:
    global _cached_user
    if _cached_user and not force_refresh:
        return _cached_user

    cfg = load_config()
    if not force_refresh and cfg.get("cached_username"):
        _cached_user = cfg["cached_username"]
        return _cached_user

    # 1. 优先检查配置或环境变量中的 Cookie
    cookie = get_reddit_cookie()
    if cookie:
        try:
            s = requests.Session()
            reload_proxies()
            if _proxies:
                s.proxies.update(_proxies)
            s.cookies.set("reddit_session", cookie, domain=".reddit.com")
            s.headers.update({
                "User-Agent": _session.headers["User-Agent"],
                "Accept": "application/json",
            })
            r = s.get("https://www.reddit.com/api/me.json", timeout=8)
            if r.status_code == 200:
                name = r.json().get("data", {}).get("name")
                if name:
                    _cached_user = f"u/{name} (Cookie)"
                    cfg["cached_username"] = _cached_user
                    save_config(cfg)
                    return _cached_user
        except Exception:
            pass

    # 2. 检测 opencli 中已登录的身份
    opencli_bin = shutil.which("opencli")
    if opencli_bin:
        try:
            res = subprocess.run([opencli_bin, "reddit", "whoami", "-f", "json"],
                                 capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                m = re.search(r'\[.*\]', res.stdout, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    for item in data:
                        if item.get("field") == "Username" and item.get("value"):
                            user_val = item["value"]
                            _cached_user = f"{user_val} (OpenCLI)"
                            cfg["cached_username"] = _cached_user
                            save_config(cfg)
                            return _cached_user
        except Exception:
            pass

    return None


def post_comment_with_cookie(parent_fullname: str, text: str, cookie: str) -> dict:
    s = requests.Session()
    reload_proxies()
    if _proxies:
        s.proxies.update(_proxies)
    s.cookies.set("reddit_session", cookie, domain=".reddit.com")
    s.headers.update({
        "User-Agent": _session.headers["User-Agent"],
        "Accept": "application/json",
    })
    
    # 验证身份并获取 modhash
    try:
        r_me = s.get("https://www.reddit.com/api/me.json", timeout=10)
        r_me.raise_for_status()
        me_data = r_me.json().get("data", {})
        username = me_data.get("name")
        if not username:
            raise PermissionError("Cookie 无效或已过期 (未识别到登录用户)")
        modhash = me_data.get("modhash", "")
    except Exception as e:
        raise PermissionError(f"Reddit 身份校验失败: {e}")

    payload = {
        "parent": parent_fullname,
        "text": text,
        "api_type": "json",
    }
    if modhash:
        payload["uh"] = modhash

    try:
        r_post = s.post("https://www.reddit.com/api/comment", data=payload, timeout=15)
        r_post.raise_for_status()
        res_data = r_post.json()
    except Exception as e:
        raise RuntimeError(f"请求 Reddit 发帖失败: {e}")

    errors = res_data.get("json", {}).get("errors", [])
    if errors:
        err_msg = "; ".join(": ".join(str(x) for x in e) for e in errors)
        raise RuntimeError(f"Reddit 拒绝发帖: {err_msg}")

    return {
        "success": True,
        "author": username,
        "message": f"由 u/{username} 成功回帖！"
    }


def post_comment_with_opencli(parent_fullname: str, text: str) -> dict:
    opencli_bin = shutil.which("opencli")
    if not opencli_bin:
        raise FileNotFoundError("未安装 opencli 命令行工具")

    if parent_fullname.startswith("t1_"):
        comment_id = parent_fullname[3:]
        cmd = [opencli_bin, "reddit", "reply", comment_id, text, "-f", "json"]
    else:
        post_id = parent_fullname.removeprefix("t3_")
        cmd = [opencli_bin, "reddit", "comment", post_id, text, "-f", "json"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    except subprocess.TimeoutExpired:
        raise TimeoutError("OpenCLI 回帖请求超时 (35秒)")

    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        clean_lines = [l for l in err.splitlines() if "Update available" not in l and "Run: npm" not in l]
        raise RuntimeError("\n".join(clean_lines) or "OpenCLI 执行失败")

    stdout = proc.stdout.strip()
    try:
        m = re.search(r'\[.*\]', stdout, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                if item.get("status") == "success":
                    return {"success": True, "message": item.get("message", "回帖成功")}
                else:
                    raise RuntimeError(item.get("message", "回帖失败"))
    except json.JSONDecodeError:
        pass

    if "success" in stdout.lower() or "posted" in stdout.lower():
        return {"success": True, "message": "回帖成功"}

    raise RuntimeError(f"未能确认回帖结果: {stdout[:200]}")


def post_comment(parent_fullname: str, text: str) -> dict:
    fullname = parent_fullname.strip()
    if not fullname.startswith("t3_") and not fullname.startswith("t1_"):
        fullname = f"t3_{fullname}"

    # 1. 若配置了 Cookie 则优先用 Cookie 直连提交（最轻量迅速）
    cookie = get_reddit_cookie()
    if cookie:
        try:
            return post_comment_with_cookie(fullname, text, cookie)
        except Exception:
            if not shutil.which("opencli"):
                raise

    # 2. 若未配 Cookie 或 Cookie 失败，自动尝试 opencli
    if shutil.which("opencli"):
        return post_comment_with_opencli(fullname, text)

    raise PermissionError(
        "未检测到 Reddit 登录凭证。\n"
        "1. 使用 opencli: 在终端运行 opencli reddit login 完成登录\n"
        "2. 使用 Cookie: 在 ~/.config/reddit-cli/config.json 中配置 reddit_session"
    )
