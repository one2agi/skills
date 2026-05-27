# 微信公众号 Cookie 获取手册

> 当 `gzh_article.py list` 报错"Cookie 可能已失效"时使用本手册。

## Cookie 保存位置

```
C:\Users\morav\.mavis\skills\wechat-article-reader\scripts\skill.env
```

每行格式：`cookie名称=cookie值`，不需要引号。

---

## 方法一：Edge 已开调试端口（推荐）

**前置条件**：Edge 已带 `--remote-debugging-port=9222` 启动，无需重启浏览器。

### 步骤 1：检查 mavis browser

```bash
mavis browser status
```

如显示 `Native host: not connected`，运行：
```bash
mavis browser install
```

### 步骤 2：验证登录态

```powershell
mavis browser tool navigate "{\`"url\`":\`"https://mp.weixin.qq.com/\`"}"
mavis browser tool query "{\`"mode\`":\`"page_text\`",\`"limit\`":100}"
```

看到"公众号"后台界面 → 已登录。继续下一步。
看到登录页面 → 未登录，改用方法二。

### 步骤 3：导出 cookies

```javascript
// get_cookies.js
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const context = browser.contexts()[0];
  const cookies = await context.cookies(['https://mp.weixin.qq.com/']);
  const fs = require('fs');
  const lines = cookies.map(c => c.name + '=' + c.value).join('\n');
  fs.writeFileSync('C:\\Users\\morav\\.mavis\\skills\\wechat-article-reader\\scripts\\skill.env', lines);
  console.log('Saved', cookies.length, 'cookies');
  await browser.close();
})();
```

```bash
cd D:\project; node get_cookies.js
```

### 步骤 4：验证

```bash
$env:PYTHONIOENCODING="utf-8"
cd "C:\Users\morav\.mavis\skills\wechat-article-reader\scripts"
python gzh_article.py list "机器之心" 3
```

看到文章列表 → 成功。

---

## 方法二：启动带调试端口的 Edge

**前置条件**：Edge 未开调试端口，或方法一失败。

### 步骤 1：重启 Edge 带调试端口

```powershell
taskkill /F /IM msedge.exe
Start-Sleep -Seconds 3
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9222"
```

### 步骤 2：验证端口已开

```bash
netstat -ano | Select-String "9222"
```

看到 `LISTENING` → 成功。

### 步骤 3：按方法一步骤 2-4 操作

---

## 永久解决方案

修改 Edge 快捷方式目标为：
```
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222
```

以后每次打开 Edge 自动带调试端口，随时可导出 cookies。

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `ECONNREFUSED` | Edge 没开调试端口 | 用方法二重启 Edge |
| `native host offline` | mavis 扩展断开 | `mavis browser install` |
| 导出成功但搜索失败 | Cookie 已过期 | 在 Edge 里重新登录 mp.weixin.qq.com |
| Session 已被占用 | 用户数据目录被占用 | 先 `taskkill /F /IM msedge.exe` 再重启 |
| PowerShell JSON 转义报错 | 命令行直接传参 | 写 `.ps1` 脚本文件，用 `` ` `` 转义 |

---

## 工作原理

- **mavis browser**：通过 Chrome 扩展桥接原生消息，操作已登录的 Edge 页面
- **playwright CDP**：通过调试端口协议读取 cookies
- 两者共用同一个 Edge 实例，mavis browser 验证登录态，playwright CDP 导出 cookies