<p align="center">
  <img src="logo.jpeg" width="120" alt="Paper Pulse logo" />
</p>

<h1 align="center">Paper Pulse</h1>

<p align="center">
  每日自动抓取 arXiv / 期刊前沿论文，通过双 LLM 完成筛选与深度分析，生成网页日报并推送邮件。
</p>

<p align="center">
  <a href="https://github.com/yanyanhuang/paper-radar/">上游仓库</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#配置">配置</a> ·
  <a href="#token--请求消耗">Token 消耗</a>
</p>

---

## 这是什么？

**Paper Pulse** 是一个自动化论文日报工具：

1. **抓取** — 每天从 arXiv RSS 和学术期刊 RSS（Nature / NEJM / Cell / Science 等）获取最新论文。
2. **筛选** — 轻量 LLM 根据你配置的关键词，从标题/摘要中快速匹配相关论文。
3. **分析** — 多模态 LLM 读取 PDF，自动提取 TLDR、主要贡献、创新点、方法、实验、数据集与代码仓库，并给出质量评分（1-10）。
4. **输出** — 生成结构化网页报告（Markdown + JSON）与邮件推送，支持在浏览器中按关键词快速浏览与检索。

Fork 自 [paper-radar](https://github.com/yanyanhuang/paper-radar/)，主要改进包括：
- 原生 arXiv 论文也写入历史去重，避免 cross-listing 导致的连日重复
- 轻量/重量 LLM 均支持多 Provider fallback 与并发分析
- 自动为 arXiv 论文附加 [AlphaXiv](https://www.alphaxiv.org/) 讨论页链接
- 邮件支持 Email Proxy API 与 SMTP 二选一
- 机构代理（EZproxy）完全配置化，不再绑定某一所学校

---

## 快速开始

```bash
git clone https://github.com/<your-username>/paper-pulse.git
cd paper-pulse

# 创建并激活虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Windows 下用 .venv\Scripts\activate

# 安装依赖
pip install -e .

cp .env.example .env
cp config.yaml.template config.yaml
# 编辑 .env 填入 API 密钥，编辑 config.yaml 设置关键词
```

### 使用 systemd 运行（推荐）

项目内置了 systemd 配置，可直接用 `systemctl` 管理 Web 服务与定时日报：

```bash
# 1. 假设你把项目放在 /opt/paper-pulse（可修改 systemd 文件中的路径）
sudo cp -r . /opt/paper-pulse
cd /opt/paper-pulse

# 2. 安装服务
sudo cp systemd/paper-pulse-web.service /etc/systemd/system/
sudo cp systemd/paper-pulse-daily.service /etc/systemd/system/
sudo cp systemd/paper-pulse-daily.timer /etc/systemd/system/

# 3. 启动 Web UI（默认端口 8080）
sudo systemctl daemon-reload
sudo systemctl enable --now paper-pulse-web

# 4. 启动定时日报（每天早上 09:10 自动运行）
sudo systemctl enable --now paper-pulse-daily.timer

# 查看状态
sudo systemctl status paper-pulse-web
sudo systemctl list-timers paper-pulse-daily.timer
```

访问 `http://<your-host>:8080` 即可浏览日报。

### 手动运行

```bash
# 只生成本地报告，不发邮件
python main.py --dry-run

# 调试模式（减少抓取量，详细日志）
python main.py --debug --dry-run

# 单独启动 Web UI
python webapp.py
```

---

## 配置

核心配置在 `config.yaml`（从模板复制）：

- **`keywords`** — 你关心的研究方向（name + description + examples）
- **`preprints`** — arXiv 分类与可选 bioRxiv / medRxiv
- **`journals`** — 期刊源开关（RSS URL 可内置回退或完全自定义）
- **`llm`** — Light（筛选）/ Heavy（PDF 分析）/ Summary（领域综述），均支持列表 fallback
- **`email`** — `mode: proxy` 或 `mode: smtp`
- **`runtime`** — 并发数、PDF 超时、自动清理 PDF 缓存天数（默认 7 天）
- **`ezproxy`** — 机构代理配置（可选），用于下载付费期刊 PDF

API 密钥通过环境变量注入（`.env`），**不会进入版本控制**。

---

## Token / 请求消耗

基于实际运行日志（日均抓取 ~400 篇，命中 ~80 篇，分析 ~70 篇）的大致推算：

| 阶段 | 日均请求 | 日均 Token |
|------|---------|-----------|
| 筛选（Light） | 300–500 | 300K–800K |
| 分析（Heavy） | 50–150 | 1M–5M |
| 总结（Summary） | 5–20 | 20K–100K |
| **合计** | **~350–670** | **~1.3M–5.9M** |

> 仅开 arXiv 时偏下限；开启多期刊且 PDF 较长时偏上限。

---

## 期刊与机构代理（EZproxy）

期刊的 RSS 抓取（标题、摘要、链接）**不需要任何登录**，直接访问公开 RSS 即可。

只有下载期刊 PDF 时才可能需要机构代理。EZproxy 支持通过环境变量完全配置化：

```bash
EZPROXY_BASE_URL="https://eproxy.lib.your-school.edu/login?url="
EZPROXY_UID="your-library-id"
EZPROXY_PIN="your-library-pin"
```

如果你所在学校不使用 EZproxy，请参考 `skills/journal-ezproxy-implementation.md` 的指南进行适配。

---

## Docker 部署（可选）

如果你更习惯容器化部署：

```bash
# 构建
docker build -t yourname/paper-pulse:latest .

# 运行（传入 .env）
docker run -d --name paper-pulse \
  --env-file .env \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd)/cache:/app/cache \
  yourname/paper-pulse:latest
```

或使用 `docker-compose.yml`：

```bash
docker compose up -d
```

---

## 目录结构

```
.
├── main.py                  # 主流程入口
├── fetcher.py               # arXiv 抓取
├── journal_fetcher.py       # 期刊 / 外部预印本抓取
├── pdf_handler.py           # PDF 下载与 EZproxy 认证
├── paper_history.py         # 跨日去重历史
├── agents/                  # LLM Agent（Filter / Analyzer / Summary）
├── models/                  # 数据模型
├── reporter.py              # Markdown / JSON / 邮件报告生成
├── webapp.py                # FastAPI 前端服务
├── web/                     # 前端静态文件
├── systemd/                 # systemd service + timer 配置
├── config.yaml.template     # 配置模板
├── .env.example             # 环境变量模板
├── skills/                  # 扩展实现指南
└── logo.jpeg                # 项目 Logo
```

---

## 许可证

MIT License
