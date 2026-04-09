# reddit-cli

Reddit 实时热榜命令行工具，支持中文翻译。

## 安装

```bash
pip install reddit-cli
```

## 使用

```bash
reddit                        # 默认刷 r/worldnews 热榜
reddit China_irl              # 指定 subreddit
reddit technology --sort new  # 最新帖子
reddit funny -l 30 -r 30      # 显示30条，30秒刷新
reddit worldnews --no-translate  # 不翻译，显示原文
```

## 参数

| 参数 | 简写 | 说明 | 默认 |
|------|------|------|------|
| `subreddit` | | 板块名称 | worldnews |
| `--sort` | `-s` | 排序：hot/new/top/rising | hot |
| `--limit` | `-l` | 显示条数 | 20 |
| `--refresh` | `-r` | 刷新间隔（秒） | 60 |
| `--no-translate` | `-T` | 不翻译，显示原文 | 默认翻译 |
