#!/usr/bin/env python3
"""
微信公众号文章综合工具

用法:
  # 原生方式
  python3 gzh_article.py fetch "<url>"                  # 抓取单篇文章
  python3 gzh_article.py list "公众号名" [数量]          # 文章列表
  python3 gzh_article.py trends "<关键词>" [--max-items N]  # 爆款查询
  python3 gzh_article.py stats "<url>"                  # 互动数据
  python3 gzh_article.py compare "<关键词>" [数量]      # 多公众号对比

  # mptext API 方式（扩展/备用）
  python3 gzh_article.py mpsearch <关键字> [数量]     # 搜索公众号
  python3 gzh_article.py mpaccount <url>                # 根据URL查公众号
  python3 gzh_article.py mparticles <fakeid> [数量]     # 获取文章列表
  python3 gzh_article.py mpinfo <fakeid>                 # 主体信息
  python3 gzh_article.py mpdownload <url> [格式]         # 下载文章
"""

import sys
import os

# 路径配置（使用绝对路径避免相对路径解析问题）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Load env variables from skill.env
from dotenv import load_dotenv
load_dotenv(os.path.join(SCRIPT_DIR, "skill.env"))

# 延迟导入子模块函数
from wechat_article import cmd_list as wechat_cmd_list
from wechat_article import cmd_full as wechat_cmd_full
from wechat_article import cmd_fetch as wechat_cmd_fetch
from wechat_article import fetch_article_by_url as wechat_fetch_article
from wechat_article import fetch_article_by_url  # keep for backward compat
from trends.api import fetch_trending_data
from trends.formatters import get_formatter
from trends.scoring import score_article
from trends.sorting import merge_and_sort
from core import safe_filename_from_keyword
from core.models import TrendingArticle, ArticleMetrics
from mptext_api import MpTextAPI, get_client as get_mptext_client
import re


def cmd_stats(url):
    """查询特定文章的互动数据"""
    # 修复 URL：添加 chksm 参数（微信抓取需要）
    if 'chksm=' not in url:
        if '#rd' in url:
            url = url.replace('#rd', '&chksm=placeholder#rd')
        else:
            url = url + '&chksm=placeholder'

    from fetch_wechat_article import fetch_wechat_article_with_title
    title, content = fetch_wechat_article_with_title(url)
    if title.startswith("FETCH_FAILED"):
        print("❌ 抓取文章失败")
        sys.exit(1)

    print(f"📄 文章: {title}\n")

    search_keywords = [
        re.sub(r'刚刚，', '', title).rstrip('！'),
        title.replace('！', '').replace('。', ''),
    ]

    found = False
    for keyword in search_keywords:
        if len(keyword) < 5:
            continue
        try:
            result = fetch_trending_data(keyword)

            # Find matching articles from all categories
            all_articles = []
            for cat_key, cat_name in [
                ('low_fan_explosive', '低粉高阅读'),
                ('ten_w_reading', '10万+阅读'),
                ('original_rank', '原创排行'),
                ('one_w_reading', '万阅读')
            ]:
                for item in result.raw_categories.get(cat_key, []):
                    article = TrendingArticle.from_api_dict(item, cat_key)
                    article.category_name = cat_name
                    all_articles.append(article)

            if not all_articles:
                continue

            # Sort and limit
            result.scored_articles = merge_and_sort(all_articles, keyword, 3)
            formatter = get_formatter(result, 'text', 3)
            print(formatter.format())
            found = True
            break
        except Exception as e:
            print(f"搜索异常: {e}")
            continue

    if not found:
        print("⚠️  未能在爆款数据库中找到该文章的互动数据")
        print("   可能原因：文章较新尚未收录，或非爆款文章")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "fetch":
        # 单篇文章抓取
        if len(sys.argv) < 3:
            print("用法: gzh_article.py fetch <url>")
            sys.exit(1)
        url = sys.argv[2]
        wechat_cmd_fetch(url)

    elif cmd == "list":
        # 公众号文章列表
        if len(sys.argv) < 3:
            print("用法: gzh_article.py list <公众号名> [数量] [--preview] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]")
            sys.exit(1)
        # 透传参数给子模块
        name = sys.argv[2]
        count = 10
        start_date = None
        end_date = None
        preview = False
        for i, arg in enumerate(sys.argv[3:]):
            if not arg.startswith("--") and arg.isdigit():
                count = int(arg)
            if arg == "--preview":
                preview = True
            if arg == "--start-date" and i + 3 < len(sys.argv):
                start_date = sys.argv[i + 4]
            if arg == "--end-date" and i + 3 < len(sys.argv):
                end_date = sys.argv[i + 4]
        if preview:
            wechat_cmd_full(name, count)
        else:
            wechat_cmd_list(name, count, start_date, end_date)

    elif cmd == "full":
        # 列表+全文预览（已废弃，使用 --preview 参数）
        print("⚠️  full 命令已废弃，请使用: gzh_article.py list <公众号名> [数量] --preview")
        print("   或直接使用: gzh_article.py list <公众号名> [数量]")
        sys.exit(1)

    elif cmd == "trends":
        # 全网爆款查询
        if len(sys.argv) < 3:
            print("用法: gzh_article.py trends <关键词> [--max-items N] [--start-date YYYY-MM-DD]")
            print("       多关键词并行: python3 gzh_article.py trends <关键词1>,<关键词2> [--max-items N]")
            sys.exit(1)

        raw_keyword = sys.argv[2]

        # Parse extra args
        max_items = 15
        start_date = None
        for i, arg in enumerate(sys.argv[3:]):
            if arg == "--max-items" and i + 4 < len(sys.argv):
                max_items = int(sys.argv[i + 4])
            if arg == "--start-date" and i + 4 < len(sys.argv):
                start_date = sys.argv[i + 4]

        # 支持多关键词并行（逗号分隔）
        keywords = [k.strip() for k in raw_keyword.split(',') if k.strip()]
        if not keywords:
            print("⚠️  关键词不能为空")
            sys.exit(1)

        import threading

        results = {}
        errors = {}

        def fetch_one(kw):
            try:
                results[kw] = fetch_trending_data(kw, start_date=start_date)
            except Exception as e:
                errors[kw] = str(e)

        if len(keywords) == 1:
            # 单关键词：直接执行
            result = fetch_trending_data(keywords[0], start_date=start_date)
        else:
            # 多关键词：threading 并行
            threads = []
            for kw in keywords:
                t = threading.Thread(target=fetch_one, args=(kw,))
                t.start()
                threads.append(t)
            for t in threads:
                t.join()

            if errors:
                for kw, err in errors.items():
                    print(f"⚠️  关键词「{kw}」查询异常: {err}")

            if not results:
                print("❌ 所有关键词查询均失败")
                sys.exit(1)

            # 合并所有关键词的原始文章
            result = None
            for kw in keywords:
                if kw in results:
                    r = results[kw]
                    if result is None:
                        result = r
                    else:
                        # 合并 raw_categories
                        for cat_key in r.raw_categories:
                            if cat_key not in result.raw_categories:
                                result.raw_categories[cat_key] = []
                            result.raw_categories[cat_key].extend(r.raw_categories[cat_key])

        # Build scored articles and sort
        scored_articles = []
        all_articles = []
        for cat_key, cat_name in [
            ('low_fan_explosive', '低粉高阅读'),
            ('ten_w_reading', '阅读靠前'),
            ('original_rank', '原创靠前'),
            ('one_w_reading', '数据增长中')
        ]:
            for item in result.raw_categories.get(cat_key, []):
                article = TrendingArticle.from_api_dict(item, cat_key)
                article.category_name = cat_name
                all_articles.append(article)
                scored = score_article(article, raw_keyword, cat_key)
                scored_articles.append(scored)

        # Sort and limit (merge_and_sort 内置 min_relevance 过滤)
        result.scored_articles = merge_and_sort(all_articles, raw_keyword, max_items)

        # 输出结果
        kw_display = ' + '.join(f'「{k}」' for k in keywords)
        formatter = get_formatter(result, 'text', max_items)
        print(formatter.format())
        print(f"\n📊 查询关键词: {kw_display}")
        print(f"📈 总数据量: {result.total_raw} 条")

    elif cmd == "stats":
        # 查询特定文章的互动数据
        if len(sys.argv) < 3:
            print("用法: gzh_article.py stats <url>")
            sys.exit(1)
        url = sys.argv[2]
        cmd_stats(url)

    elif cmd == "compare":
        # 多公众号对比
        # 用法:
        #   python3 gzh_article.py compare "<关键词>" [数量]           # 关键词模式（无需Cookie）
        #   python3 gzh_article.py compare --accounts 量子位,AI科技迷     # 指定公众号（需要Cookie）
        #   python3 gzh_article.py compare --urls "<url1>","<url2>"      # 指定链接（需要Cookie）

        from trends.analysis import group_by_account, generate_comparison_table, AccountStats
        from core import format_number
        from datetime import datetime

        account_names = None
        urls = None
        keyword = None
        count = 10

        # 解析参数
        account_names = None
        urls = None
        keyword = None
        count = 10

        args = sys.argv[2:]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--accounts" and i + 1 < len(args):
                account_names = [a.strip() for a in args[i + 1].split(",")]
                i += 2
            elif arg == "--urls" and i + 1 < len(args):
                urls = [u.strip() for u in args[i + 1].split(",")]
                i += 2
            elif arg == "--max-items" and i + 1 < len(args):
                count = int(args[i + 1])
                i += 2
            elif arg.startswith("--"):
                i += 1
            else:
                keyword = arg
                i += 1

        all_articles = []

        if account_names or urls:
            # 模式A/B: 指定公众号或链接（需要Cookie）
            from wechat_article import load_cookie, get_token, search_fakeid, get_article_list, get_account_by_biz

            cookie = load_cookie()
            if not cookie:
                print("❌ 需要微信 Cookie，请配置 scripts/skill.env")
                sys.exit(1)

            token = get_token(cookie)
            if not token:
                print("❌ 获取 token 失败，Cookie 可能已失效")
                sys.exit(1)

            # 从 URLs 提取公众号并获取文章
            if urls:
                print(f"🔍 从 {len(urls)} 个链接提取公众号...\n")
                for url in urls:
                    # 从 URL 提取 biz
                    biz = None
                    if "__biz=" in url:
                        biz = url.split("__biz=")[1].split("&")[0]
                    elif "biz=" in url:
                        biz = url.split("biz=")[1].split("&")[0]
                    if not biz:
                        print(f"  ⚠️  无法从链接提取 biz: {url[:50]}...")
                        continue

                    print(f"  📰 biz: {biz}")
                    fakeid, nickname = get_account_by_biz(cookie, token, biz)
                    if not fakeid:
                        print(f"    ❌ 未找到对应的公众号")
                        continue
                    print(f"    ✅ 找到: {nickname}，获取文章...")

                    articles = get_article_list(cookie, token, fakeid, count)
                    print(f"    📄 获取到 {len(articles)} 篇文章")

                    # 转换为 TrendingArticle 格式
                    for art in articles:
                        m = ArticleMetrics(
                            like_count=art.get("like_count", 0),
                            comment_count=art.get("comment_count", 0),
                            share_count=art.get("share_count", 0),
                            clicks_count=0
                        )
                        article = TrendingArticle(
                            photo_id=art.get("aid", ""),
                            title=art.get("title", ""),
                            summary="",
                            account_id=fakeid,
                            account_name=nickname,
                            fans=0,
                            public_time=datetime.fromtimestamp(art.get("create_time", 0)).strftime("%Y-%m-%d") if art.get("create_time") else "",
                            metrics=m,
                            ori_url=art.get("link", ""),
                            cover_url="",
                            category_key="",
                            category_name="公众号文章"
                        )
                        all_articles.append(article)

            # 获取指定公众号的文章
            if account_names:
                print(f"📊 对比 {len(account_names)} 个公众号...\n")

                for name in account_names:
                    print(f"🔍 搜索公众号: {name}")
                    fakeid, nickname = search_fakeid(cookie, token, name)
                    if not fakeid:
                        print(f"  ❌ 未找到公众号: {name}")
                        continue
                    print(f"  ✅ 找到: {nickname}，获取文章...")

                    articles = get_article_list(cookie, token, fakeid, count)
                    print(f"  📄 获取到 {len(articles)} 篇文章")

                    # 转换为 TrendingArticle 格式
                    for art in articles:
                        m = ArticleMetrics(
                            like_count=art.get("like_count", 0),
                            comment_count=art.get("comment_count", 0),
                            share_count=art.get("share_count", 0),
                            clicks_count=0
                        )
                        article = TrendingArticle(
                            photo_id=art.get("aid", ""),
                            title=art.get("title", ""),
                            summary="",
                            account_id=fakeid,
                            account_name=nickname,
                            fans=0,
                            public_time=datetime.fromtimestamp(art.get("create_time", 0)).strftime("%Y-%m-%d") if art.get("create_time") else "",
                            metrics=m,
                            ori_url=art.get("link", ""),
                            cover_url="",
                            category_key="",
                            category_name="公众号文章"
                        )
                        all_articles.append(article)

                if not all_articles:
                    print("❌ 未获取到任何文章数据")
                    sys.exit(1)

        else:
            # 模式C: 关键词搜索（无需Cookie）
            if not keyword:
                print("用法: gzh_article.py compare <关键词> [数量]")
                print("   或: gzh_article.py compare --accounts 量子位,AI科技迷")
                print("   或: gzh_article.py compare --urls \"<url1>\",\"<url2>\"")
                sys.exit(1)

            print(f"📊 搜索关键词: {keyword}")
            result = fetch_trending_data(keyword)
            for cat_key, cat_name in [
                ('low_fan_explosive', '低粉高阅读'),
                ('ten_w_reading', '10万+阅读'),
                ('original_rank', '原创排行'),
                ('one_w_reading', '万阅读')
            ]:
                for item in result.raw_categories.get(cat_key, []):
                    article = TrendingArticle.from_api_dict(item, cat_key)
                    article.category_name = cat_name
                    all_articles.append(article)

        stats = group_by_account(all_articles)
        keyword_display = keyword or (",".join(account_names) if account_names else "指定链接")
        print(generate_comparison_table(stats[:count], keyword_display))

    elif cmd == "mpsearch":
        # mptext API: 搜索公众号
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mpsearch <关键字> [数量]")
            sys.exit(1)
        keyword = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        
        client = get_mptext_client()
        accounts = client.search_account(keyword, size=size)
        
        if not accounts:
            print(f"No accounts found for keyword '{keyword}'")
            sys.exit(0)
        
        print(f"Found {len(accounts)} accounts:\n")
        for i, acc in enumerate(accounts, 1):
            print(f"{i}. {acc.nickname} (ID: {acc.fakeid})")
            if acc.alias:
                print(f"   Alias: {acc.alias}")
            print()

    elif cmd == "mparticles":
        # mptext API: 获取文章列表
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mparticles <fakeid> [数量]")
            sys.exit(1)
        fakeid = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        
        client = get_mptext_client()
        articles = client.get_articles(fakeid, size=size)
        
        if not articles:
            print("No articles found")
            sys.exit(0)
        
        print(f"Found {len(articles)} articles:\n")
        for i, art in enumerate(articles, 1):
            print(f"{i}. {art.title}")
            print(f"   Link: {art.link}")
            print()

    elif cmd == "mpaccount":
        # mptext API: 根据文章URL获取公众号信息
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mpaccount <url>")
            sys.exit(1)
        url = sys.argv[2]
        
        client = get_mptext_client()
        acc = client.get_account_by_url(url)
        
        if not acc:
            print("Account not found")
            sys.exit(1)
        
        print(f"Account: {acc.nickname}")
        print(f"ID: {acc.fakeid}")
        if acc.alias:
            print(f"Alias: {acc.alias}")

    elif cmd == "mpinfo":
        # mptext API: 查询公众号主体信息
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mpinfo <fakeid>")
            sys.exit(1)
        fakeid = sys.argv[2]
        
        client = get_mptext_client()
        info = client.get_author_info(fakeid)
        
        print(f"Identity: {info.get('identity_name', 'Unknown')}")
        print(f"Verified: {'Yes' if info.get('is_verify') else 'No'}")
        print(f"Original articles: {info.get('original_article_count', 0)}")

    elif cmd == "mpdownload":
        # mptext API: 下载文章
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mpdownload <url> [格式]")
            sys.exit(1)
        url = sys.argv[2]
        fmt = sys.argv[3] if len(sys.argv) > 3 else 'text'
        
        client = get_mptext_client()
        content = client.download_article(url, format=fmt)
        
        if not content:
            print("[WARN] Article content is empty")
            sys.exit(1)
        
        content = content.replace('\xa0', ' ').replace('\u3000', ' ')
        sys.stdout.reconfigure(encoding='utf-8')
        print(content)

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
