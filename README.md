# Project Causality (因果律) - 智能异动归因 Agent

## 项目简介

这是一个基于 **Map-Reduce (分治与归并)** 思想的智能金融分析系统。

为了解决大规模分析时的“算力浪费”问题（例如：银行板块大涨，没必要对 10 只银行股分别调用 10 次 LLM 进行重复分析），本项目引入了 **“双层架构”** 设计：

*   **Layer 1: 调度层 (The Dispatcher)** —— 负责量化扫描、归类、去重。
*   **Layer 2: 执行层 (The Worker)** —— 负责执行 LangGraph 归因任务。

---

## 🚀 核心架构升级 (v3.0 - Map-Reduce)

### 架构流程图

```mermaid
graph TD
    subgraph Layer1_Dispatcher [Layer 1: 调度层 (Python Quant Logic)]
        Input[输入: 股票列表] --> Scan[Quant Scan: 扫描与计算]
        Scan --> Decision{代码逻辑判别}
        Decision -->|Abs(个股-行业)<2%| Group_S[放入板块桶 (Sector Bucket)]
        Decision -->|Abs(个股-龙头)<3%| Group_C[放入概念桶 (Concept Bucket)]
        Decision -->|其他| Group_I[放入个股桶 (Individual Bucket)]
        
        Group_S -->|Merge| Task_S[生成 1 个板块分析任务]
        Group_C -->|Merge| Task_C[生成 1 个概念分析任务]
        Group_I -->|Keep| Task_I[生成 N 个个股分析任务]
    end

    subgraph Layer2_Worker [Layer 2: 执行层 (LangGraph Agent)]
        Task_S --> Agent_Run[Agent 执行: 搜索 & 归因]
        Task_C --> Agent_Run
        Task_I --> Agent_Run
    end

    Agent_Run --> Result[生成通用报告]
    Result --> Distribute[分发 (Distribute)]
    Distribute --> Stock_A[股票 A]
    Distribute --> Stock_B[股票 B]
    Distribute --> Stock_C[股票 C]
```

---

## 🧠 双层架构详解

### Layer 1: 调度层 (The Dispatcher)
这一层**不调用 LLM**，纯粹使用 Python 逻辑进行快速的量化算术运算，实现“预分组” (Pre-grouping)。

**1. 扫描 (Scan)**
快速获取所有目标股票的 `Change` (涨跌幅), `Sector_Change` (行业涨跌幅), `Concept_Change` (概念龙头涨跌幅)。

**2. 归类 (Shuffle/Group)**
根据硬性规则将股票扔进不同的“桶”：
*   **板块共振桶**: `abs(个股 - 行业) < 2.0%`。
    *   *例子*: [招商银行, 兴业银行, 平安银行] -> 全部扔进 "银行板块" 桶。
*   **概念跟风桶**: `abs(个股 - 概念龙头) < 3.0%`。
    *   *例子*: [歌尔股份, 立讯精密] -> 全部扔进 "消费电子" 桶。
*   **独立行情桶**: 不满足上述条件。
    *   *例子*: [宁德时代] (假设只有它特立独行)。

**3. 任务生成 (Reduce)**
*   银行板块桶 -> 生成 **1 个** 任务：“分析银行板块今日利好”。
*   消费电子桶 -> 生成 **1 个** 任务：“分析消费电子今日利好”。
*   宁德时代 -> 生成 **1 个** 任务：“分析宁德时代今日异动”。
*   *效果*: 原本需要分析 6 只股票（调用 6 次 Agent），现在只需要调用 3 次。

### Layer 2: 执行层 (The Worker)
这一层是标准的 **LangGraph Agent**，负责接收具体的“分析主题”并执行深度的搜寻与推理。

*   **Input**: 任务类型 (板块/概念/个股) + 目标名称 (如 "银行板块")。
*   **Nodes**:
    *   `Search_Node`: 针对性搜索 (宏观/行业/个股)。
    *   `Report_Eval_Node`: 生成归因报告并自我打分。
*   **Output**: 一份高质量的归因报告。

### 后处理: 分发 (Distribute)
调度器拿到 Worker 返回的“银行板块报告”后，将其**复制**分发给桶里的每一只股票（招商银行、兴业银行...），作为它们的最终解释。

---

## 🛠️ Prompts 设计 (针对 Worker 层)

由于“分类”已经由 Layer 1 的 Python 代码完成，Layer 2 的 Prompt 只需要专注于**针对已知类型**的分析。

### 1. 归因分析 Prompt (通用版)
```python
REPORT_PROMPT = """
你是一个 A 股归因分析师。
当前任务目标：{target_name}
任务类型：{task_type} (SECTOR / CONCEPT / STOCK)

请根据搜索结果撰写分析报告：
- 如果是 SECTOR (板块)：重点寻找宏观政策、行业利好、资金流向。
- 如果是 CONCEPT (概念)：重点寻找龙头股效应、突发题材消息。
- 如果是 STOCK (个股)：重点寻找个股公告、业绩、特定传闻。

请生成一段简练、专业的归因结论。
"""
```

---

## 🚀 快速开始

### 1. 环境配置
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 运行
```bash
# 启动 Streamlit 应用
streamlit run app.py
```
*(注：app.py 内部将集成 Dispatcher -> LangGraph 的调用逻辑)*
