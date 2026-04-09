import requests
import time
import html

HEADERS = {"User-Agent": "reddit-cli/0.2.0"}


def fetch_posts(subreddit, sort="hot", limit=20):
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()["data"]["children"]


def fetch_comments(permalink, limit=20):
    url = f"https://www.reddit.com{permalink}.json?limit={limit}&depth=2"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    post = data[0]["data"]["children"][0]["data"]
    comments_raw = data[1]["data"]["children"]
    comments = []
    for c in comments_raw:
        if c["kind"] != "t1":
            continue
        d = c["data"]
        comments.append({
            "author": d.get("author", "[deleted]"),
            "body": html.unescape(d.get("body", "")),
            "score": d.get("score", 0),
            "replies": _extract_replies(d.get("replies", "")),
        })
    return post, comments


def _extract_replies(replies):
    if not replies or not isinstance(replies, dict):
        return []
    children = replies.get("data", {}).get("children", [])
    result = []
    for c in children:
        if c["kind"] != "t1":
            continue
        d = c["data"]
        result.append({
            "author": d.get("author", "[deleted]"),
            "body": html.unescape(d.get("body", "")),
            "score": d.get("score", 0),
        })
    return result[:3]


def search_posts(query, subreddit=None, limit=20):
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=1&limit={limit}"
    else:
        url = f"https://www.reddit.com/search.json?q={query}&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()["data"]["children"]


def search_subreddits(query, limit=10):
    url = f"https://www.reddit.com/subreddits/search.json?q={query}&limit={limit}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
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
