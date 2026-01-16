import os
import streamlit as st
from langchain_openai import ChatOpenAI

# 从 Streamlit Secrets 或环境变量加载 API Key
def get_ark_api_key():
    if "ARK_API_KEY" in st.secrets:
        return st.secrets["ARK_API_KEY"]
    return os.getenv("ARK_API_KEY")

def init_llm():
    """
    初始化 LangChain ChatOpenAI 客户端 (适配 Volcengine Ark)。
    """
    api_key = get_ark_api_key()
    if not api_key:
        raise ValueError("❌ 未在 secrets.toml 或环境变量中找到 ARK_API_KEY。")
    
    # 使用 ChatOpenAI 封装
    llm = ChatOpenAI(
        model="deepseek-v3-2-251201", # 将模型名称统一配置在这里
        openai_api_key=api_key,
        openai_api_base="https://ark.cn-beijing.volces.com/api/v3",
        temperature=0.3 # 降低温度以获得更稳定的评估结果
    )
    return llm

# --- Prompts ---

EVALUATE_PROMPT = """
你是一个严谨的 A 股归因分析师。
你的任务是根据搜索结果，评估其是否足以解释【{target_name}】的异动原因。

【当前任务】
任务类型：{task_type} (SECTOR/CONCEPT/STOCK)
目标名称：{target_name}

【搜索结果摘要】
{search_results}

【评估要求】
1. 是否找到了核心驱动力？(如：政策文件、业绩预告、明确的传闻、龙头股效应)
2. 信息时效性如何？(是否为近日消息)
3. 逻辑是否自洽？

请输出 JSON 格式：
{{
    "confidence_score": 0.xx,  // 0.0-1.0, >0.6 表示通过
    "reflection": "自我反思：为什么给这个分？如果分数低，缺什么信息？",
    "reasoning_summary": "简要的归因逻辑摘要 (1-2句话)"
}}
"""

REPORT_PROMPT = """
你是一个专业的 A 股财经主笔。请基于提供的搜索结果，为【{target_name}】撰写一份高质量的异动归因快报。

【任务详情】
任务类型：{task_type} 
目标名称：{target_name}
涉及股票：{involved_stocks}

【搜索结果】
{search_results}

【撰写要求】
1. **标题**: 简练有力，突出核心原因 (例如：“央行降准利好落地，银行板块集体爆发”)。
2. **正文**: 采用“总-分”结构。
   - 第一段：直接给出结论（上涨/下跌的主因）。
   - 第二段：引用搜索结果中的具体证据（政策、公告、资金流向等）。
   - 第三段（如果是板块/概念）：简述龙头股表现或板块联动情况。
3. **语气**: 专业、客观、叙事感强，避免堆砌数据。
4. **格式**: Markdown。

请直接输出 markdown 格式的报告内容。
"""

QUERY_OPTIMIZE_PROMPT = """
上一次搜索的关键词是："{old_query}"
搜索结果评估不理想 (分数为 {score})。
反思原因：{reflection}

请生成一个新的搜索关键词，尝试从不同的角度切入。
- 如果搜不到原因 -> 试着搜“传闻”、“股吧”、“小作文”。
- 如果噪音太大 -> 增加“公告”、“官方”限定词。
- 如果是概念跟风 -> 搜该概念的其他龙头名字。

注意：不要在搜索关键词中添加时间限定词

只输出新的关键词字符串，不要包含其他内容。
"""
