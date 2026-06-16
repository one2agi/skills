---
name: wechat-article-reader
description: "Use when user shares a WeChat public account article link, asks to search/list articles by account name, queries trending articles by keyword, or needs WeChat article content read and summarized. Also triggers on: 批量抓取, 批量下载, 公众号文章, 微信文章, 爆款查询, 文章分析."
metadata:
  {
    "openclaw":
      {
        "allowed-tools": ["exec", "read", "write", "edit"],
      },
  }
---

# 微信公众号文章读取器

## Contents

- [视图一：目标 → 路径链路](#视图一目标--路径链路)
- [视图二：原子功能索引](#视图二原子功能索引)
- [降级决策规则](#降级决策规则)
- [依赖状态与配置](#依赖状态与配置)

---

## 视图一：目标 → 路径链路

> 每个目标有多少种路径可走，哪种最快（优先级最高），失败后降级到哪种。

### 目标：分析正文

**输入：** 文章链接 / 文章标题 / 文章URL（任意形态）

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **URL → fetch P1**（Cookie→js_content） | Cookie | ~80% | 最完整，优先尝试 |
| P2 | **URL → fetch P2**（curl多UA） | 无 | ~60% | P1失败时降级，不需要Cookie |
| P3 | **URL → fetch P3**（mptext下载） | API key | ~70% | P2失败后降级 |
| P4 | **URL → fetch P4**（mptext→og:title） | API key | ~50% | P3返回空时的兜底 |
| P5 | **标题 → resolve → fetch P1** | Cookie | ~60% | 先把标题转成URL，再走P1 |
| P6 | **浏览器兜底** | mavis-browser | ~90% | 所有API失效后的最终兜底 |

```
[URL] → P1(failed) → P2(failed) → P3(failed) → P4
[标题] → resolve → [URL] → P1(failed) → P2(failed) → P3(failed) → P4 → 浏览器
```

---

### 目标：查公众号文章列表

**输入：** 公众号名称 / 文章链接 / 文章标题

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **公众号名 → list P1**（原生API） | Cookie | ~90% | 直接用公众号名搜索，最快 |
| P2 | **公众号名 → list P2**（mptext） | API key | ~80% | P1失败时降级 |
| P3 | **URL → biz提取 → list_ex**（mparticles_by_url） | Cookie | ~90% | URL直接提取biz，跳过搜索 |
| P4 | **标题 → resolve → list P1** | Cookie | ~50% | 标题→关键词→搜公众号→拿列表，慢但不依赖公众号名 |
| P5 | **标题 → trends → mpsearch → list** | Cookie | ~30% | 先查爆款库，再找对应公众号 |

```
[公众号名] → P1(failed) → P2
[URL]     → biz提取 → P1
[标题]    → resolve → P1(failed) → P2
[标题]    → trends → mpsearch → list (低优先级)
```

---

### 目标：搜索公众号

**输入：** 关键字 / 公众号名

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **关键字 → mpsearch P2**（mptext搜索） | API key | ~90% | 纯API调用，不需要Cookie，最快 |
| P2 | **公众号名 → mpsearch P1**（原生searchbiz） | Cookie | ~90% | Cookie方式，稳定性稍差 |
| P3 | **URL → mpaccount**（mptext accountbyurl） | API key | ~90% | 从URL反向查公众号信息 |

---

### 目标：查公众号信息

**输入：** 文章链接 / fakeid

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **URL → mpaccount**（mptext accountbyurl） | API key | ~90% | 从URL直接获取元信息，最快 |
| P2 | **URL → biz提取 → get_account_by_biz** | Cookie | ~80% | 从biz反向查公众号名 |
| P3 | **fakeid → mpinfo**（authorinfo） | API key | ~90% | 查主体公司信息 |

---

### 目标：查互动数据

**输入：** 文章链接 / 文章标题

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **URL → stats P1**（trends API） | 无 | ~60% | 直接从爆款库查，新文章可能未收录 |
| P2 | **URL → fetch P1 → 分析正文** | Cookie | ~80% | 拿正文后自己数阅读/在看/转发 |

---

### 目标：全网爆款查询

**输入：** 关键词

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **关键词 → trends P1**（爆款API） | 无 | ~90% | 直接查爆款库，支持多关键词并行 |

> 泛化词治理：见 `references/trends-guide.md`

---

### 目标：根据标题找链接

**输入：** 文章标题

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **标题 → resolve**（mpsearch→list→相似度匹配） | Cookie | ~70% | 提取关键词→搜公众号→拿文章→标题匹配，精度高 |
| P2 | **标题 → trends → 取链接** | 无 | ~30% | 在爆款库中搜标题，准确但依赖收录 |
| P3 | **浏览器Google搜索** | mavis-browser | ~60% | 兜底方案，需要人工筛选 |

---

### 目标：多公众号对比

**输入：** 关键词 / 公众号列表 / URL列表

| 优先级 | 路径 | 依赖 | 成功率 | 说明 |
|---|---|---|---|---|
| P1 | **关键词 → compare P1**（trends API） | 无 | ~90% | 多关键词并行查爆款，适合趋势分析 |
| P2 | **公众号列表 → compare P2**（原生list） | Cookie | ~90% | 指定公众号，精度高 |
| P3 | **URL列表 → compare P3**（biz→list） | Cookie | ~90% | 从URL提取biz，对比多个号 |

---

## 视图二：原子功能索引

### 原子功能卡片

| # | 原子功能 | 核心能力 | 输入 | 输出 |
|---|---|---|---|---|
| A1 | **fetch** | 抓文章正文 | URL | title + content |
| A2 | **list** | 按公众号名查文章列表 | 公众号名 | [{title, link, create_time, ...}] |
| A3 | **list_ex** | 从fakeid/biz查文章列表 | fakeid/biz | [{title, link, create_time, ...}] |
| A4 | **search_fakeid** | 从关键字搜公众号 | 关键字 | (fakeid, nickname) |
| A5 | **mpsearch** | mptext搜索公众号 | 关键字 | [{nickname, fakeid, ...}] |
| A6 | **mpaccount** | 从URL查公众号元信息 | URL | {nickname, fakeid, alias, ...} |
| A7 | **mparticles_by_url** | URL→biz→list_ex | URL | [{title, link, ...}] |
| A8 | **get_account_by_biz** | 从biz反查公众号 | biz | (fakeid, nickname) |
| A9 | **resolve** | 标题→链接（组合功能） | 标题 | (best_url, best_title) |
| A10 | **trends** | 查爆款文章 | 关键词 | TrendingResult |
| A11 | **stats** | 查互动数据 | URL | {like, comment, read} |
| A12 | **mpinfo** | 查公众号主体信息 | fakeid | {identity_name, is_verify, ...} |
| A13 | **compare** | 多公众号对比 | 关键词/名单/URL | 对比表格 |

### 原子功能依赖矩阵

| 原子功能 | 需要Cookie | 需要API key | 成功率 | 调用次数限制 |
|---|---|---|---|---|
| fetch P1/P2 | P1需要/P2不需要 | 不需要 | ~80% / ~60% | 无明确限制 |
| list / list_ex | ✅ | 不需要 | ~90% | 最大436篇 |
| search_fakeid | ✅ | 不需要 | ~90% | — |
| mpsearch P1/P2 | P1需要/P2不需要 | P2需要 | ~90% | — |
| mpaccount | ❌ | ✅ | ~90% | — |
| mparticles_by_url | ✅ | ❌ | ~90% | — |
| get_account_by_biz | ✅ | ❌ | ~80% | count需≥5 |
| resolve | ✅ | ❌ | ~70% | — |
| trends | ❌ | ❌ | ~90% | 泛化词可能无结果 |
| stats | ❌ | ❌ | ~60% | 新文章可能未收录 |
| mpinfo | ❌ | ✅ | ~90% | — |
| compare | 部分需要 | ❌ | ~90% | — |

---

## 降级决策规则

1. **P1 失败 → P2**，不要在 P1 卡死重试超过 2 次
2. **P2 失败 → P3**，依此类推，不要跳过
3. **返回字数 < 200** = 这次失败，换下一条路
4. **Cookie 相关失败**：提示用户 Cookie 可能失效，见 cookie-guide.md 修复
5. **所有 API 失效**：启用浏览器兜底（`mavis-browser` 截图 + 图像理解）

---

## 依赖状态与配置

| 依赖 | 配置文件 | 失效表现 | 修复方式 |
|---|---|---|---|
| Cookie | `scripts/skill.env` | token 获取失败 / API返回ret≠0 | 见 cookie-guide.md 重新获取 |
| API Key (mptext) | `scripts/skill.env` | 401 / 403 错误 | 更换 MPTEXT_API_KEY |
| 浏览器兜底 | mavis-browser 已连接 | — | 截图 + describe_images OCR |

---

## 局限性

- **fetch**：部分文章（含 x-wechat-key 验证）只能拿到摘要/开头，约 800-1000 字
- **list / list_ex**：原生 API 最多约 436 篇，更早历史无法翻到
- **stats**：仅对爆款文章有效，新文章直接用 fetch 分析正文
- **resolve**：依赖公众号在搜索结果中命中，标题过于泛化可能导致匹配失败
- **get_account_by_biz**：list_ex 要求 count≥5，否则返回空列表

---

## 快速参考

```
# 分析正文（最快）
python3 gzh_article.py fetch "<url>"

# 公众号文章列表
python3 gzh_article.py list "公众号名"
python3 gzh_article.py mparticles_by_url "<url>"

# 搜索公众号
python3 gzh_article.py mpsearch "<关键字>"

# 爆款查询
python3 gzh_article.py trends "关键词"

# 根据标题找链接
python3 gzh_article.py resolve "<文章标题>"

# 互动数据
python3 gzh_article.py stats "<url>"

# 多公众号对比
python3 gzh_article.py compare "<关键词>"
python3 gzh_article.py compare --accounts 量子位,AI科技迷
python3 gzh_article.py compare --urls "<url1>","<url2>"
```