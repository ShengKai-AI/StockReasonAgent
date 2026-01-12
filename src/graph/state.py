from typing import TypedDict, Optional
from src.dispatcher import AnalysisTask

class GraphState(TypedDict):
    """
    定义 LangGraph 工作流的状态结构。
    """
    task: AnalysisTask         # Layer 1 传入的任务
    
    # 搜索上下文
    search_query: Optional[str]     # 当前搜索关键词
    search_results: Optional[str]   # Tavily 搜索结果摘要
    
    # 报告与评估
    report_content: Optional[str]   # 归因报告草稿
    confidence_score: float         # 置信度 (0.0 到 1.0)
    reflection: Optional[str]       # 自我反思 / 打分理由
    
    # 循环控制
    loop_count: int                 # 重试计数器 (从 0 开始)
