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
  python3 gzh_article.py resolve "<文章标题>"            # 根据标题找链接

  # mptext API 方式（扩展/备用）
  python3 gzh_article.py mpsearch <关键字> [数量]     # 搜索公众号
  python3 gzh_article.py mpaccount <url>                # 根据URL查公众号
  python3 gzh_article.py mparticles <fakeid> [数量]     # 获取文章列表
  python3 gzh_article.py mparticles_by_url <url> [数量]  # 从URL获取文章列表
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
    sys.stdout.reconfigure(encoding='utf-8')
    # 修复 URL：添加 chksm 参数（微信抓取需要）
    if 'chksm=' not in url:
        if '#rd' in url:
            url = url.replace('#rd', '&chksm=placeholder#rd')
        else:
            url = url + '&chksm=placeholder'

    from fetch_wechat_article import fetch_wechat_article_with_title
    title, content = fetch_wechat_article_with_title(url)
    if title.startswith("FETCH_FAILED"):
        print("文章抓取失败")
        sys.exit(1)

    print(f"文章: {title}\n")

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

            result.scored_articles = merge_and_sort(all_articles, keyword, 3)
            formatter = get_formatter(result, 'text', 3)
            print(formatter.format())
            found = True
            break
        except Exception as e:
            print(f"搜索异常: {e}")
            continue


def cmd_resolve(title):
    """根据标题找链接：标题→关键词→mpsearch→list→标题匹配"""
    sys.stdout.reconfigure(encoding='utf-8')
    from wechat_article import load_cookie, get_token, search_fakeid, get_article_list

    cookie = load_cookie()
    if not cookie:
        print("需要 Cookie，请配置 scripts/skill.env")
        sys.exit(1)
    token = get_token(cookie)
    if not token:
        print("获取 token 失败，Cookie 可能已失效")
        sys.exit(1)

    stop_words = {'的', '是', '了', '在', '和', '不', '啊', '吗', '呢', '吧',
                  '你', '我', '他', '她', '它', '这', '那', '都', '很', '就',
                  '做', '能', '会', '说', '要', '让', '被', '把', '对', '给',
                  '一个', '什么', '怎么', '为什么', '如何', '有没有', '好吗'}
    words = re.findall(r'[\u4e00-\u9fff]{2,8}', title)
    keywords = [w for w in words if w not in stop_words and len(w) >= 2]
    full_title_clean = re.sub(r'[^\u4e00-\u9fff\w]', '', title)
    if len(full_title_clean) >= 4:
        keywords.append(full_title_clean)

    print(f"[resolve] 标题: {title}")
    print(f"[resolve] 关键词: {keywords}\n")

    matched = []

    for kw in keywords[:5]:
        fakeid, nickname = search_fakeid(cookie, token, kw)
        if not fakeid:
            continue
        print(f"  [{kw}] 找到公众号: {nickname}")

        articles = get_article_list(cookie, token, fakeid, 20)
        if not articles:
            continue

        title_lower = title.lower()
        for art in articles:
            art_title = art.get('title', '').lower()
            common = sum(1 for c in art_title if c in title_lower)
            if len(art_title) > 0:
                score = common / min(len(title_lower), len(art_title))
                if score > 0.5 or title_lower[:10] in art_title:
                    link = art.get('link', '')
                    display_title = art.get('title', '')[:40]
                    print(f"    [match] {display_title}")
                    print(f"           {link}")
                    matched.append((score, art, nickname))

    if not matched:
        print("[resolve] 未找到匹配的文章")
        sys.exit(1)

    matched.sort(key=lambda x: x[0], reverse=True)
    best_score, best_art, best_nick = matched[0]
    print(f"[resolve] 最佳匹配 ({best_nick}): {best_art.get('title', '')[:50]}")
    print(f"[resolve] URL: {best_art.get('link', '')}")


def cmd_trends(args):
    """爆款查询"""
    sys.stdout.reconfigure(encoding='utf-8')
    import argparse
    parser = argparse.ArgumentParser(description='爆款查询')
    parser.add_argument('keywords', nargs='+', help='关键词（逗号分隔多词）')
    parser.add_argument('--max-items', type=int, default=10)
    parser.add_argument('--start-date', default=None)
    parsed, unknown = parser.parse_known_args(args)
    keywords = parsed.keywords[0].split(',') if parsed.keywords else []
    raw_keyword = ','.join(keywords)
    max_items = parsed.max_items

    if not keywords:
        print("关键词不能为空")
        sys.exit(1)

    results = {}
    errors = {}
    threads = []

    def fetch_one(kw):
        try:
            results[kw] = fetch_trending_data(kw, max_retries=2)
        except Exception as e:
            errors[kw] = str(e)

    for kw in keywords:
        import threading
        t = threading.Thread(target=fetch_one, args=(kw,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    if errors:
        for kw, err in errors.items():
            print(f"关键词[{kw}]查询异常: {err}")

    if not results:
        print("所有关键词查询均失败")
        sys.exit(1)

    merged_result = None
    for kw in keywords:
        if kw in results:
            r = results[kw]
            if merged_result is None:
                merged_result = r
            else:
                for cat_key in r.raw_categories:
                    if cat_key not in merged_result.raw_categories:
                        merged_result.raw_categories[cat_key] = []
                    merged_result.raw_categories[cat_key].extend(r.raw_categories[cat_key])

    all_articles = []
    for cat_key, cat_name in [
        ('low_fan_explosive', '低粉高阅读'),
        ('ten_w_reading', '阅读靠前'),
        ('original_rank', '原创靠前'),
        ('one_w_reading', '数据增长中')
    ]:
        for item in merged_result.raw_categories.get(cat_key, []):
            article = TrendingArticle.from_api_dict(item, cat_key)
            article.category_name = cat_name
            all_articles.append(article)

    merged_result.scored_articles = merge_and_sort(all_articles, raw_keyword, max_items)
    formatter = get_formatter(merged_result, 'text', max_items)
    print(formatter.format())
    print(f"查询关键词: {raw_keyword}")
    print(f"总数据量: {merged_result.total_raw} 条")


def cmd_compare(args):
    """多公众号对比"""
    sys.stdout.reconfigure(encoding='utf-8')
    from datetime import datetime

    account_names = None
    urls = None
    keyword = None
    count = 10

    i = 0
    while i < len(args):
        if args[i] == "--accounts":
            account_names = args[i+1].split(',') if i+1 < len(args) else []
            i += 2
        elif args[i] == "--urls":
            urls = args[i+1].split(',') if i+1 < len(args) else []
            i += 2
        elif args[i] == "--count":
            count = int(args[i+1]) if i+1 < len(args) else 10
            i += 2
        elif args[i].startswith('--'):
            i += 1
        else:
            keyword = args[i]
            i += 1

    all_articles = []

    if keyword:
        result = fetch_trending_data(keyword, max_retries=2)
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
        result.scored_articles = merge_and_sort(all_articles, keyword, count * 3)
        formatter = get_formatter(result, 'text', count)
        print(formatter.format())
        print(f"查询关键词: {keyword}")
        print(f"总数据量: {result.total_raw} 条")
        return

    if account_names or urls:
        from wechat_article import load_cookie, get_token, search_fakeid, get_article_list

        cookie = load_cookie()
        if not cookie:
            print("需要 Cookie，请配置 scripts/skill.env")
            sys.exit(1)
        token = get_token(cookie)
        if not token:
            print("获取 token 失败，Cookie 可能已失效")
            sys.exit(1)

        if urls:
            print(f"从 {len(urls)} 个链接提取公众号...\n")
            for url in urls:
                biz = None
                if "__biz=" in url:
                    biz = url.split("__biz=")[1].split("&")[0]
                elif "biz=" in url:
                    biz = url.split("biz=")[1].split("&")[0]
                if not biz:
                    print(f"  无法从链接提取 biz: {url[:50]}...")
                    continue

                fakeid, nickname = search_fakeid(cookie, token, biz) or (biz, "")
                if not fakeid:
                    print(f"  未找到对应的公众号")
                    continue

                articles = get_article_list(cookie, token, fakeid, count)
                print(f"  {nickname}: {len(articles)} 篇文章")

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

        if account_names:
            print(f"对比 {len(account_names)} 个公众号...\n")
            for name in account_names:
                fakeid, nickname = search_fakeid(cookie, token, name)
                if not fakeid:
                    print(f"  未找到公众号: {name}")
                    continue

                articles = get_article_list(cookie, token, fakeid, count)
                print(f"  {nickname}: {len(articles)} 篇文章")

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

        if all_articles:
            from trends.analysis import group_by_account, generate_comparison_table
            groups = group_by_account(all_articles)
            table = generate_comparison_table(groups)
            print(table)
        return


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if cmd == "fetch":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py fetch <url>")
            sys.exit(1)
        url = sys.argv[2]
        wechat_fetch_article(url)

    elif cmd == "list":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py list <公众号名> [数量] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--preview]")
            sys.exit(1)
        args = sys.argv[2:]
        wechat_cmd_list(args)

    elif cmd == "full":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py full <公众号名> [数量]")
            sys.exit(1)
        args = sys.argv[2:]
        wechat_cmd_full(args)

    elif cmd == "stats":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py stats <url>")
            sys.exit(1)
        url = sys.argv[2]
        cmd_stats(url)

    elif cmd == "trends":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py trends <关键词> [--max-items N] [--start-date YYYY-MM-DD]")
            sys.exit(1)
        args = sys.argv[2:]
        cmd_trends(args)

    elif cmd == "compare":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py compare <关键词> [数量]")
            print("       gzh_article.py compare --accounts <name1>,<name2>...")
            print("       gzh_article.py compare --urls <url1>,<url2>...")
            sys.exit(1)
        args = sys.argv[2:]
        cmd_compare(args)

    elif cmd == "mpsearch":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mpsearch <关键字> [数量]")
            sys.exit(1)
        keyword = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        client = get_mptext_client()
        results = client.search_account(keyword, size=size)
        for r in results:
            print(f"  {r.get('nickname', '?')} (fakeid={r.get('fakeid', '?')})")

    elif cmd == "mpaccount":
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

    elif cmd == "mparticles":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mparticles <fakeid> [数量]")
            sys.exit(1)
        fakeid = sys.argv[2]
        size = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        client = get_mptext_client()
        articles = client.get_articles(fakeid, size=size)
        for art in articles:
            print(f"  {art.get('title', '?')}")
            print(f"  {art.get('url', '')}")

    elif cmd == "mparticles_by_url":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py mparticles_by_url <url> [数量]")
            sys.exit(1)
        url = sys.argv[2]
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 10

        from wechat_article import load_cookie, get_token, get_article_list
        cookie = load_cookie()
        if not cookie:
            print("需要 Cookie，请配置 scripts/skill.env")
            sys.exit(1)
        token = get_token(cookie)
        if not token:
            print("获取 token 失败，Cookie 可能已失效")
            sys.exit(1)

        biz = None
        if "__biz=" in url:
            biz = url.split("__biz=")[1].split("&")[0]
        elif "biz=" in url:
            biz = url.split("biz=")[1].split("&")[0]
        if not biz:
            print("无法从链接提取 biz")
            sys.exit(1)

        articles = get_article_list(cookie, token, biz, count)
        if not articles:
            print("未获取到文章")
            sys.exit(1)
        print(f"共 {len(articles)} 篇文章：")
        for i, art in enumerate(articles, 1):
            print(f"{i}. {art.get('title', '无标题')}")
            print(f"   {art.get('link', '')}")

    elif cmd == "mpinfo":
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

    elif cmd == "resolve":
        if len(sys.argv) < 3:
            print("用法: gzh_article.py resolve \"<文章标题>\"")
            sys.exit(1)
        title = sys.argv[2]
        cmd_resolve(title)

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()