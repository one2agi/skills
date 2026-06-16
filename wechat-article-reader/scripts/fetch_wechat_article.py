#!/usr/bin/env python3
"""
微信公众号文章内容提取脚本
用法: python3 fetch_wechat_article.py "<url>"
策略：requests + Cookie + js_content 提取 > og:title meta fallback > curl 多UA兜底
"""

import sys
import re
import os
import html


def fetch_wechat_article(url: str) -> str:
    """使用 requests + Cookie 获取微信文章全文内容"""
    title, content = fetch_wechat_article_with_title(url)
    if content.startswith("FETCH_FAILED"):
        return content
    return content


def _extract_title_from_html(html_text: str) -> str:
    """从 HTML 中提取文章标题"""
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
    if m:
        return html.unescape(m.group(1))
    m = re.search(r'<title>([^<]+)</title>', html_text)
    return html.unescape(m.group(1)) if m else ""


def _extract_js_content(html_text: str) -> str:
    """
    从新版微信 HTML 中提取正文（js_content 结构已变，不再使用 id="js_content"）
    新策略：找到包含正文内容的 section，逐步缩小范围
    """
    # 新版微信：正文内容在 <section> 标签内，找 img_common 附近的 rich_media_content
    # 先尝试直接找正文容器
    content_sections = [
        'id="img-content"',
        'id="js_content"',
        'class="rich_media_content"',
        'id="rich_media_content"',
    ]

    for section in content_sections:
        idx = html_text.find(section)
        if idx == -1:
            continue

        # 找到这个 section 之后的 HTML 片段
        snippet = html_text[idx:]
        # 截取前 500KB 应该足够包含全文
        snippet = snippet[:500000]

        # 找终止标记
        end_markers = ['id="js_pc_qr_code"', 'id="runtime_config"', '</section>']
        end_pos = len(snippet)
        for marker in end_markers:
            pos = snippet.find(marker)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        raw = snippet[:end_pos]
        # 去掉所有 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', raw)
        # 处理 HTML 实体
        for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                              ("&gt;", ">"), ("&mdash;", "—"), ("&ldquo;", '"'),
                              ("&rdquo;", '"'), ("&lsquo;", "'"), ("&rsquo;", "'")]:
            text = text.replace(entity, char)
        # 清理空白
        text = re.sub(r'style="visibility: hidden; opacity: 0; "\s*>\s*', '', text)
        text = re.sub(r'预览时标签不可点.*', '', text)
        text = re.sub(r'var\s+first_sceen__time.*', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) >= 200:
            return text

    return ""


def _extract_og_fallback(html_text: str) -> str:
    """
    og:title meta fallback：当 js_content 提取失败时，从 og:title 拿摘要/开头
    og:title 内容包含文章开头段落（已 HTML 转义）
    """
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
    if not m:
        return ""

    raw = m.group(1)
    content = html.unescape(raw)
    content = re.sub(r'\\n', '\n', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def _extract_via_requests(url: str, cookie: str) -> tuple:
    """策略1：requests + Cookie 提取正文"""
    import requests as req

    if not url.startswith("https://mp.weixin.qq.com"):
        url = "https://mp.weixin.qq.com/s/" + url.split("/s/")[-1]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie,
        "Referer": "https://mp.weixin.qq.com/",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    r = req.get(url, headers=headers, allow_redirects=True, timeout=30)
    html_text = r.text

    if len(html_text) < 1000 or "环境异常" in html_text:
        return "", ""

    title = _extract_title_from_html(html_text)

    # 优先：用 js_content 提取正文
    content = _extract_js_content(html_text)

    # Fallback 1：og:title meta 拿摘要
    if len(content) < 200:
        content = _extract_og_fallback(html_text)

    return title, content


def _extract_via_curl(url: str) -> tuple:
    """策略2：curl 多 UA 兜底（无 Cookie）"""
    import subprocess

    strategies = [
        {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36", "referer": "https://mp.weixin.qq.com/"},
        {"ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1", "referer": "https://www.google.com/"},
        {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", "referer": "https://www.google.com/"},
    ]

    for strat in strategies:
        cmd = ["curl", "-s", "-L", "-A", strat["ua"],
               "-H", f"Referer: {strat['referer']}",
               "--connect-timeout", "15", "--max-time", "30", url]

        result = subprocess.run(cmd, capture_output=True, text=False)
        html_text = result.stdout.decode("utf-8", errors="replace")

        if len(html_text) < 1000:
            continue
        if "环境异常" in html_text or "请选择验证方式" in html_text:
            continue

        title = _extract_title_from_html(html_text)
        content = _extract_js_content(html_text)
        if len(content) < 200:
            content = _extract_og_fallback(html_text)

        if len(content) >= 200:
            return title, content

    return "", ""


def fetch_wechat_article_with_title(url: str) -> tuple:
    """
    获取微信文章正文和标题
    优先级：requests + Cookie > curl 多UA
    提取策略：js_content 正文 > og:title meta fallback
    返回：(title, content)，content 最短 200 字符才算成功
    """
    # 加载 Cookie
    cookie = ""
    cookie_file = os.path.join(os.path.dirname(__file__), "skill.env")
    if os.path.exists(cookie_file):
        sys.path.insert(0, os.path.dirname(__file__))
        try:
            from wechat_article import load_cookie
            cookie = load_cookie() or ""
        except Exception:
            cookie = ""

    # 策略1：requests + Cookie（优先）
    if cookie:
        try:
            title, content = _extract_via_requests(url, cookie)
            if len(content) >= 200:
                return title, content
        except Exception:
            pass

    # 策略2：curl 多 UA 兜底（无 Cookie 也能跑）
    try:
        title, content = _extract_via_curl(url)
        if len(content) >= 200:
            return title, content
    except Exception:
        pass

    return "FETCH_FAILED: 所有策略均失败，文章可能被拦截或不存在", ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 fetch_wechat_article.py <微信文章URL>")
        sys.exit(1)

    url = sys.argv[1]
    content = fetch_wechat_article(url)

    if content.startswith("FETCH_FAILED"):
        print(content)
        sys.exit(1)
    else:
        print(content)