import json
from src.graph.state import GraphState
from src.tools.search_tools import run_search
from src.llm.model import init_llm, EVALUATE_PROMPT, REPORT_PROMPT, QUERY_OPTIMIZE_PROMPT

llm_client = init_llm()

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
            current_query = f"{task.target_name} 行业 利好 政策 消息"
        elif task.task_type == "CONCEPT":
            current_query = f"{task.target_name} 概念 龙头股 异动原因"
        else: # STOCK
            current_query = f"{task.target_name} {task.involved_stocks[0]} 公告 传闻 利好"
        
        state['search_query'] = current_query
        print(f"🔹 [节点: 搜索] 生成初始搜索词: {current_query}")

    # 2. 执行搜索
    print(f"🔹 [节点: 搜索] 执行搜索: {current_query}")
    results = run_search(current_query)
    
    # 3. 更新状态
    state['search_results'] = results
    return state

def node_evaluate(state: GraphState) -> GraphState:
    """
    使用 LLM 评估搜索结果。
    输出: confidence_score (置信度), reflection (反思)
    """
    task = state['task']
    results = state['search_results']
    
    print(f"🔹 [节点: 评估] 正在评估结果质量...")
    
    # 构建 Prompt
    prompt = EVALUATE_PROMPT.format(
        task_type=task.task_type,
        target_name=task.target_name,
        search_results=results
    )
    
    try:
        completion = llm_client.chat.completions.create(
            model="deepseek-v3-2-251201", # 确保此 ID 与实际配置一致
            messages=[{"role": "user", "content": prompt}]
        )
        content = completion.choices[0].message.content
        
        # 解析 JSON 输出 (简单解析)
        # 尝试查找被 markdown 包裹的 JSON 块
        cleaned_content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_content)
        
        score = float(data.get("confidence_score", 0.0))
        reflection = data.get("reflection", "未提供反思内容。")
        
        state['confidence_score'] = score
        state['reflection'] = reflection
        print(f"  -> 得分: {score}, 反思: {reflection[:50]}...")
        
    except Exception as e:
        print(f"❌ [节点: 评估] 错误: {e}")
        state['confidence_score'] = 0.0
        state['reflection'] = f"评估过程中发生错误: {str(e)}"

    return state

def node_report(state: GraphState) -> GraphState:
    """
    使用 LLM 撰写最终报告。
    """
    task = state['task']
    results = state['search_results']
    
    print(f"🔹 [节点: 报告] 正在撰写报告...")
    
    prompt = REPORT_PROMPT.format(
        task_type=task.task_type,
        target_name=task.target_name,
        involved_stocks=", ".join(task.involved_stocks),
        search_results=results
    )
    
    try:
        completion = llm_client.chat.completions.create(
            model="deepseek-v3-2-251201", 
            messages=[{"role": "user", "content": prompt}]
        )
        report = completion.choices[0].message.content
        state['report_content'] = report
        print(f"  -> 报告已生成 ({len(report)} 字符).")
        
    except Exception as e:
        state['report_content'] = f"生成报告失败: {e}"
        
    return state

def node_optimize_query(state: GraphState) -> GraphState:
    """
    优化节点: 基于反思生成更好的搜索词。
    """
    old_query = state['search_query']
    score = state['confidence_score']
    reflection = state['reflection']
    
    print(f"🔹 [节点: 优化] 正在优化搜索词...")
    
    prompt = QUERY_OPTIMIZE_PROMPT.format(
        old_query=old_query,
        score=score,
        reflection=reflection
    )
    
    try:
        completion = llm_client.chat.completions.create(
            model="deepseek-v3-2-251201", 
            messages=[{"role": "user", "content": prompt}]
        )
        new_query = completion.choices[0].message.content.strip()
        state['search_query'] = new_query
        state['loop_count'] = state.get('loop_count', 0) + 1
        print(f"  -> 新搜索词: {new_query} (循环次数: {state['loop_count']})")
        
    except Exception as e:
        print(f"❌ [节点: 优化] 错误: {e}")
        # 如果优化失败，尝试简单追加
        state['search_query'] = old_query + " 官方公告"
        state['loop_count'] = state.get('loop_count', 0) + 1

    return state
