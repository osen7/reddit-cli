import sys
import io
import click

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


@click.command()
@click.argument("subreddit", required=False)
@click.option("--translate/--no-translate", "-t/-T", default=True, help="是否翻译成中文")
@click.option("--proxy", "-p", default=None, help="手动指定代理 (如 http://127.0.0.1:1082)")
@click.option("--cookie", "-c", default=None, help="配置 Reddit 登录 Cookie (reddit_session)")
@click.option("--whoami", is_flag=True, default=False, help="查看当前 Reddit 登录账号")
def main(subreddit, translate, proxy, cookie, whoami):
    """Reddit 中文实时热榜 CLI"""
    import os
    if proxy:
        os.environ["http_proxy"] = proxy
        os.environ["https_proxy"] = proxy
        os.environ["all_proxy"] = proxy

    if whoami:
        from .api import get_current_user
        user = get_current_user(force_refresh=True)
        if user:
            click.echo(f"👤 当前登录账号: {user}")
        else:
            click.echo("⚠️ 未检测到登录账号。可通过 opencli reddit login 登录，或运行 reddit --cookie <cookie> 配置。")
        return

    if cookie:
        from .api import set_reddit_cookie, get_current_user
        set_reddit_cookie(cookie)
        user = get_current_user(force_refresh=True)
        click.echo(f"✓ Cookie 已保存！当前登录身份: {user or '已配置'}")
        return

    from .app import RedditApp
    app = RedditApp(initial_subreddit=subreddit)
    app.run()
