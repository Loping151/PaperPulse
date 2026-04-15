# Skill: 为非 HKU 机构实现完整的期刊抓取与 PDF 代理

> 本指南面向希望为 **Paper Pulse**（或上游 paper-radar）适配自己学校/机构图书馆代理的开发者。

---

## 1. 期刊抓取的架构分离

Paper Pulse 的期刊相关代码集中在两个模块：

| 模块 | 职责 | 是否需要修改 |
|------|------|-------------|
| `journal_fetcher.py` | 从期刊 RSS 抓取标题、摘要、作者、链接 | 通常**不需要**修改代码，只需在 `config.yaml` 中配置 |
| `pdf_handler.py` | 下载 PDF。对付费墙内容，通过 `EZproxyPDFHandler` 进行机构代理认证 | **可能需要**修改或扩展，如果你的学校不使用标准 EZproxy |

### 1.1 内置期刊 RSS 清单

`journal_fetcher.py` 中有一个 `JOURNAL_RSS_FEEDS` 字典，作为**默认回退**。你完全可以在 `config.yaml` 中覆盖或扩展它，而无需改动代码：

```yaml
journals:
  enabled: true
  sources:
    - name: "Nature"
      key: "nature"
      enabled: true
      # 显式指定 rss_url，覆盖内置默认值
      rss_url: "https://www.nature.com/nature.rss"
    - name: "My School Journal"
      key: "my_school_journal"
      enabled: true
      rss_url: "https://journal.myschool.edu/feed.rss"
```

抓取逻辑：
1. 读取 `config.yaml` 中启用的期刊列表
2. 若配置了 `rss_url`，直接使用；否则回退到 `JOURNAL_RSS_FEEDS.get(key)`
3. 用 `feedparser` 解析 RSS，取最近 7 天的文章
4. 过滤掉新闻/评论（如 Nature 的 `d41586-xxx` 文章）
5. 通过 `paper_history.json` 去重

---

## 2. 标准 EZproxy 适配（大多数学校）

如果你的学校使用 **EZproxy**（最常见的图书馆代理方案），则只需配置环境变量，**零代码修改**。

### 2.1 获取你学校的 EZproxy 信息

以 MIT 为例：
- 登录页（Base URL）：`https://libproxy.mit.edu/login?url=`
- 用户名/密码：你的图书馆账号
- 登录表单字段：通常是 `userid` / `password`

### 2.2 配置环境变量

在 `.env` 中写入：

```bash
EZPROXY_BASE_URL=https://libproxy.mit.edu/login?url=
EZPROXY_UID=your-username
EZPROXY_PIN=your-password
```

如果登录表单字段名不同（如 `username` / `passwd`），补充：

```bash
EZPROXY_USERNAME_FIELD=username
EZPROXY_PASSWORD_FIELD=passwd
EZPROXY_SUBMIT_SELECTOR="button[type='submit']"
```

### 2.3 配置 `config.yaml`

```yaml
ezproxy:
  enabled: true
  headless: true
  base_url: "${EZPROXY_BASE_URL}"
  # 可选：如果表单字段与默认值不同
  # username_field: "username"
  # password_field: "passwd"
  # submit_selector: "button[type='submit']"
```

### 2.4 如何验证代理生效

运行一次 dry-run 并观察日志：

```bash
python main.py --debug --dry-run
```

你应能在日志中看到：
- `Performing EZproxy login for UID: abc***`
- `Login successful after Xs`

若看到 `Login timeout`，请检查：
1. `EZPROXY_BASE_URL` 是否以 `login?url=` 结尾
2. `EZPROXY_UID` / `EZPROXY_PIN` 是否正确
3. 登录页是否需要 Duo/2FA（目前 Selenium 自动登录无法处理需要手动点的 2FA）

---

## 3. 非标准代理的扩展方案

如果你的学校不使用 EZproxy，而是以下几种方案之一，你需要继承/扩展 `pdf_handler.py`：

- **Shibboleth / SAML**（跳转到学校统一身份认证）
- **OpenAthens**
- **VPN + 内网直链**
- **Token / Cookie 代理**

### 3.1 实现一个新的 PDF Handler

在 `pdf_handler.py` 中新建一个类，继承 `PDFHandler`（或 `EZproxyPDFHandler`）：

```python
class MySchoolPDFHandler(PDFHandler):
    """Custom handler for My School's institutional access."""

    def __init__(self, timeout=120, cache_dir=None, headless=True):
        super().__init__(timeout=timeout, cache_dir=cache_dir)
        self.headless = headless
        # 加载你的凭证或 session token
        self.token = os.getenv("MYSCHOOL_ACCESS_TOKEN", "")

    def download_as_base64(self, url: str, **kwargs) -> Optional[str]:
        # 1. 构造带认证的请求
        headers = {"Authorization": f"Bearer {self.token}"}
        # 2. 或者先用 Selenium 走一遍 SAML 登录，拿到 cookie 后再用 requests 下载
        # ...
        response = self._session.get(url, headers=headers, timeout=self.timeout)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        return None
```

然后在 `main.py` 中替换 `EZproxyPDFHandler` 的实例化：

```python
# 原代码
# ezproxy_handler = EZproxyPDFHandler(...)

# 替换为
from pdf_handler import MySchoolPDFHandler
ezproxy_handler = MySchoolPDFHandler(
    timeout=config.get("runtime", {}).get("pdf_timeout", 120),
    cache_dir="./cache/pdfs",
    headless=True,
)
```

### 3.2 典型场景：SAML/Shibboleth 登录

很多学校的流程是：
1. 点击期刊 PDF 链接 -> 302 到学校的 IdP 登录页
2. 输入用户名密码 -> 302 回期刊网站，并带上 `SAMLResponse`
3. 期刊网站设置 session cookie
4. 后续 PDF 下载使用此 cookie

实现建议：
- 用 `selenium` 完成步骤 1-3，拿到 cookie
- 把 cookie 注入 `requests.Session`
- 后续下载全部走 `requests.Session`

可以参考 `EZproxyPDFHandler` 的 `_perform_login`、`_save_cookies`、`_load_cookies_to_session` 方法进行移植。

---

## 4. 添加新的期刊源（完整示例）

假设你要添加一个尚未内置的期刊 `JAMA`，步骤如下：

### 4.1 找到 RSS 地址

以 JAMA 为例，RSS 地址为：
`https://jamanetwork.com/rss/site_3/67.xml`

### 4.2 在 `config.yaml` 中添加

```yaml
journals:
  enabled: true
  sources:
    - name: "JAMA"
      key: "jama"
      enabled: true
      rss_url: "https://jamanetwork.com/rss/site_3/67.xml"
```

### 4.3 （可选）补充 PDF 链接解析

如果 `journal_fetcher.py` 现有的 `_extract_pdf_url` 无法从 RSS 中正确提取该期刊的 PDF 直链，你可以补充一条解析规则：

```python
# 在 _extract_pdf_url 中添加
if "jamanetwork.com" in link:
    # 假设文章页 URL 为 https://jamanetwork.com/journals/jama/article-abstract/2812345
    # PDF 链接模式为 .../articlepdf/2812345/jama_2024_12345.pdf
    article_id = link.split("/")[-1]
    return f"https://jamanetwork.com/journals/jama/articlepdf/{article_id}"
```

### 4.4 测试

```bash
python -c "
from journal_fetcher import JournalFetcher
config = {'journals': [{'name':'JAMA','key':'jama','enabled':True,'rss_url':'https://jamanetwork.com/rss/site_3/67.xml'}], 'max_papers_per_journal': 5}
fetcher = JournalFetcher(config)
papers = fetcher.get_papers(debug=True)
print(f'Fetched {len(papers)} papers')
for p in papers:
    print(f'  {p.title} -> {p.pdf_url}')
"
```

---

## 5. 常见问题排查

### Q1: 期刊 RSS 能抓到标题摘要，但 PDF 下载 403/付费墙
A: 说明你已开启期刊但缺少有效的机构代理。请检查 `EZPROXY_BASE_URL` 与凭证是否正确，或你的学校是否使用了非 EZproxy 方案。

### Q2: 登录成功但 PDF 仍然下载失败
A: 某些期刊的 EZproxy 域名转换规则可能不是标准的 "dash-replacement"（如 `www.nature.com` -> `www-nature-com.eproxy.xxx.edu`）。你可以在 `_convert_to_ezproxy_url` 中针对该期刊添加特例。

### Q3: 双因素认证 (2FA) 阻断自动登录
A: 目前 Selenium 方案无法自动处理需要手动点击的 2FA（如 Duo Push）。 workaround：
- 先手动用浏览器登录一次，导出 cookie，放入 `cache/ezproxy_cookies.pkl`
- 或改用 VPN 方案，让容器/宿主机全程走 VPN，无需代理登录

### Q4: 不想处理 PDF，只想要标题摘要
A: 在 `config.yaml` 中关闭 `ezproxy.enabled`。期刊论文仍会出现在日报中（标题、摘要、TLDR），只是缺少 Stage 2 的详细方法/实验/贡献分析。

---

## 6. 交付检查清单

当你为某个新机构完成适配后，请确认：

- [ ] `config.yaml` 中正确配置了期刊源与 `rss_url`
- [ ] `.env` 中配置了代理相关的环境变量（或确认不需要代理）
- [ ] `journal_fetcher.py` 的 `_extract_pdf_url` 能正确返回目标期刊的 PDF 链接
- [ ] `pdf_handler.py` 中的 Handler 能成功认证并下载 PDF
- [ ] 运行 `python main.py --debug --dry-run` 无报错，且日志中出现 `Successfully analyzed X papers`
