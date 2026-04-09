import sys
import io
import click

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


@click.command()
@click.option("--translate/--no-translate", "-t/-T", default=True, help="是否翻译成中文")
def main(translate):
    """Reddit 中文实时热榜 CLI"""
    from .app import RedditApp
    app = RedditApp()
    app.run()
