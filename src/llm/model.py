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

REPORT_PROMPT = """
你是一个专业的 A 股财经主笔。请基于提供的【精选新闻】，为【{target_name}】撰写一份高质量的异动归因快报。

【任务详情】
任务类型：{task_type} 
目标名称：{target_name}
涉及股票：{involved_stocks}

【精选搜索结果】
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
我们找到了一些新闻，但它们被认为是低质量或无关的。

【被拒绝的新闻及原因】
{rejected_reasons}

请生成一个新的搜索关键词，尝试避开上述无效信息，从新的角度切入寻找【{target_name}】的异动原因。
- 重点关注：官方公告、行业政策、突发传闻。
- 避免：再次搜索已经被证明无效的方向。

注意：不要在搜索关键词中添加时间限定词

只输出新的关键词字符串，不要包含其他内容。
"""
