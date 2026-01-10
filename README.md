# Project Causality (因果律) - 智能异动归因 Agent

## 项目简介

这是一个基于 AI Agent 的智能金融分析工具，旨在解决量化与主观投资中的“归因分析”痛点。Agent 能够输入股票代码和日期，不仅展示涨跌幅，还能通过动态业务画像和多层搜索推理，给出股价异动的具体叙事原因（Narrative Attribution）。

## 核心功能

1. **动态业务画像 (Dynamic Profiling)**: 基于最新财报/公告，动态生成业务成分（如“80% AI 算力 + 20% 游戏”），而非传统的静态行业分类。
2. **异动归因推理 (Attribution Reasoning)**: 自动抓取新闻、逻辑推理，区分“板块贝塔”、“个股阿尔法”或“资金博弈”，输出涨跌的叙事逻辑。

## 技术架构

* **Agent 框架**: LangGraph (用于编排复杂的异动侦探工作流)
* **LLM**: DeepSeek-V3 / Qwen-2.5 (擅长中文与 A 股逻辑)
* **数据源**: AkShare (A 股行情/板块/公告), Tavily/Serper (网络搜索)
* **前端**: Streamlit (K线图 + 归因报告展示)
* **部署**: Docker

## 目录结构 (Project Structure)

```text
StockReasonAgent/
├── README.md               # 项目文档
├── requirements.txt        # 依赖库
├── .env.example            # 环境变量配置模板
├── src/
│   ├── main.py             # 主入口
│   ├── graph/              # LangGraph 工作流定义
│   │   ├── __init__.py
│   │   ├── state.py        # Agent 状态定义 (State)
│   │   ├── nodes.py        # 节点逻辑 (数据快照, 关键词生成, 搜索, 归因)
│   │   └── workflow.py     # 图构建 (Graph Construction)
│   ├── tools/              # 工具集
│   │   ├── __init__.py
│   │   ├── akshare_tools.py # AkShare 数据获取工具
│   │   └── search_tools.py  # 搜索 API 工具
│   ├── llm/                # 大模型配置
│   │   ├── __init__.py
│   │   └── model.py        # LLM 初始化与 Prompt 模板
│   └── ui/                 # Streamlit 前端
│       └── app.py          # 界面代码
```

## 核心工作流 (Workflow)

基于“洋葱剥皮法”的归因逻辑：

1. **数据快照 (Snapshot)**: 获取今日涨跌、换手率、所属概念板块。判断是否为板块共振。
2. **关键词生成 (Keyword Gen)**: 如果是个股异动，基于“股票名+概念”生成多维度搜索词（事实/关联/时间窗）。
3. **搜寻与清洗 (Search)**: 执行多层搜索，过滤噪音（如股吧灌水），保留权威信源。
4. **归因裁决 (The Judge)**: LLM 汇总信息，进行因果推理，输出最终归因报告。

## 快速开始

1. 环境配置:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. 设置 API Key (在 .env 中配置 DeepSeek 和 Search API Key)。
3. 运行应用:
   ```bash
   streamlit run src/ui/app.py
   ```
