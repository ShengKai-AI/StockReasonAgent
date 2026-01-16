import json
from src.graph.state import GraphState
from src.tools.search_tools import run_search
from src.llm.model import init_llm, REPORT_PROMPT, QUERY_OPTIMIZE_PROMPT
from src.llm.small_model import SmallModelClient

llm = init_llm()
small_model = SmallModelClient()

def node_search(state: GraphState) -> GraphState:
    """
    执行搜索。
    如果搜索词不存在，则基于任务生成一个初始搜索词。
    """
    task = state['task']
    current_query = state.get('search_query')
    
    # 1. 如果为空，生成初始搜索词
    if not current_query:
        if task.task_type == "SECTOR":
            current_query = f"{task.target_name} 行业 政策 消息"
        elif task.task_type == "CONCEPT":
            current_query = f"{task.target_name} 概念 龙头股"
        else: # STOCK
            current_query = f"{task.target_name} {task.involved_stocks[0]} 公告 传闻"
        
        state['search_query'] = current_query
        print(f"🔹 [节点: 搜索] 生成初始搜索词: {current_query}")

    # 2. 执行搜索
    print(f"🔹 [节点: 搜索] 执行搜索: {current_query}")
    results = run_search(current_query)
    
    # 3. 更新状态
    state['search_results'] = results
    return state

def _format_results_for_llm(results):
    if isinstance(results, list):
        if not results: return "未找到有效新闻。"
        lines = []
        for item in results:
             lines.append(f"- [{item.get('title')}]({item.get('url')}): {item.get('content', '')[:300]}...")
        return "\n\n".join(lines)
    return str(results)

from concurrent.futures import ThreadPoolExecutor, as_completed

def node_evaluate(state: GraphState) -> GraphState:
    """
    使用小模型 (Ollama) 对搜索结果进行并行评分和过滤。
    """
    task = state['task']
    results = state['search_results']
    
    print(f"🔹 [节点: 评估] 正在使用小模型并行评分 ({len(results)} 条)...")
    
    if 'all_scored_news' not in state:
        state['all_scored_news'] = []
        
    filtered_this_round = []
    
    SCORE_THRESHOLD = 0.7 # 0.7分及以上保留 (修正为 0.7 对应 0-1 范围，或者如果小模型输出 0-10 则需调整)
    
    def process_item(item):
        """单个处理函数"""
        analysis = small_model.analyze(
            news_content=item.get('content', '')[:1000],
            target_name=task.target_name
        )
        item_with_score = item.copy()
        item_with_score['score'] = analysis['score']
        item_with_score['reason'] = analysis['reason']
        return item_with_score

    # 并行执行，最大并发 4
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_item = {executor.submit(process_item, item): item for item in results}
        
        for future in as_completed(future_to_item):
            try:
                processed_item = future.result()
                score = processed_item['score']
                
                # 存入全量历史
                state['all_scored_news'].append(processed_item)
                
                if score >= SCORE_THRESHOLD:
                    filtered_this_round.append(processed_item)
                    print(f"  ✅ 保留 (分:{score}): {processed_item['title'][:20]}...")
                else:
                    print(f"  ❌ 拒绝 (分:{score}): {processed_item['title'][:20]}... 原因: {processed_item['reason'][:20]}")
            except Exception as e:
                 print(f"  ❌ 处理出错: {e}")

    # 更新 filtered_news (累加策略)
    if 'filtered_news' not in state:
        state['filtered_news'] = []
    
    state['filtered_news'].extend(filtered_this_round)
    
    print(f"  -> 当前累计高质量新闻: {len(state['filtered_news'])} 条")
    return state

def node_report(state: GraphState) -> GraphState:
    """
    使用 LLM 撰写最终报告。
    支持 Fallback 逻辑。
    """
    task = state['task']
    filtered = state.get('filtered_news', [])
    loop_count = state.get('loop_count', 0)
    
    used_news = filtered
    
    # Fallback 逻辑: 如果是最后一次尝试且高质量新闻不足 2 条，则强行取 Top 3
    if len(filtered) < 2 and loop_count >= 3:
        print("⚠️ [节点: 报告] 高质量新闻不足，触发 Fallback (Top 3)")
        all_news = state.get('all_scored_news', [])
        # 按分数降序
        sorted_news = sorted(all_news, key=lambda x: x['score'], reverse=True)
        used_news = sorted_news[:3]
        state['filtered_news'] = used_news # 更新为这些新闻以便下文引用
    
    print(f"🔹 [节点: 报告] 正在撰写报告 (使用 {len(used_news)} 条素材)...")
    
    # 转换为字符串供 LLM 阅读
    results_str = _format_results_for_llm(used_news)
    
    prompt = REPORT_PROMPT.format(
        task_type=task.task_type,
        target_name=task.target_name,
        involved_stocks=", ".join(task.involved_stocks),
        search_results=results_str
    )
    
    try:
        response = llm.invoke(prompt)
        report = response.content
        state['report_content'] = report
        print(f"  -> 报告已生成 ({len(report)} 字符).")
        
    except Exception as e:
        state['report_content'] = f"生成报告失败: {e}"
        
    return state

def node_optimize_query(state: GraphState) -> GraphState:
    """
    优化节点: 基于被拒绝新闻的原因生成新搜索词。
    """
    old_query = state['search_query']
    all_news = state.get('all_scored_news', [])
    
    # 提取最近一轮的低分新闻原因
    low_score_news = [n for n in all_news if n['score'] < 7]
    recent_low = low_score_news[-5:] # 只取最后5个，避免Prompt过长
    
    reasons_str = "\n".join([f"- 标题: {n['title']}\n  原因: {n['reason']}" for n in recent_low])
    
    print(f"🔹 [节点: 优化] 正在优化搜索词...")
    
    if not reasons_str:
        reasons_str = "暂无具体拒绝原因 (可能由于网络原因小模型调用失败)"
    
    prompt = QUERY_OPTIMIZE_PROMPT.format(
        target_name=state['task'].target_name,
        old_query=old_query,
        rejected_reasons=reasons_str
    )
    
    try:
        response = llm.invoke(prompt)
        new_query = response.content.strip()
        state['search_query'] = new_query
        state['loop_count'] = state.get('loop_count', 0) + 1
        print(f"  -> 新搜索词: {new_query} (循环次数: {state['loop_count']})")
        
    except Exception as e:
        print(f"❌ [节点: 优化] 错误: {e}")
        state['search_query'] = old_query + " 官方公告"
        state['loop_count'] = state.get('loop_count', 0) + 1

    return state
