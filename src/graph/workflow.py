from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.graph.nodes import (
    node_search, 
    node_evaluate, 
    node_report, 
    node_optimize_query
)

def check_score(state: GraphState):
    """
    条件逻辑:
    - 如果得分 > 0.6: 跳转到报告 (结束)
    - 如果得分 <= 0.6 且循环次数 < 3: 优化搜索词 -> 重新搜索
    - 如果得分 <= 0.6 且循环次数 >= 3: 跳转到报告 (强制结束)
    """
    score = state.get('confidence_score', 0.0)
    loop_count = state.get('loop_count', 0)
    
    if score > 0.6:
        return "accepted"
    
    if loop_count >= 3:
        return "max_retry"
    
    return "retry"

def create_worker_graph():
    """
    构建 Layer 2 Worker 的 LangGraph 工作流。
    """
    workflow = StateGraph(GraphState)
    
    # 添加节点
    workflow.add_node("search", node_search)
    workflow.add_node("evaluate", node_evaluate)
    workflow.add_node("report", node_report)
    workflow.add_node("optimize", node_optimize_query)
    
    # 添加边
    workflow.set_entry_point("search")
    
    workflow.add_edge("search", "evaluate")
    
    # 条件边
    workflow.add_conditional_edges(
        "evaluate",
        check_score,
        {
            "accepted": "report",
            "max_retry": "report", # 即使置信度低也强制输出
            "retry": "optimize"
        }
    )
    
    workflow.add_edge("optimize", "search")
    workflow.add_edge("report", END)
    
    # 编译
    app = workflow.compile()
    return app
