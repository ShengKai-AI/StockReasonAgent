import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 确保可以从根目录导入 stock.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.tools.akshare_tools import AkShareTool
except ImportError:
    # 如果导入失败，尝试回退/调试路径
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.tools.akshare_tools import AkShareTool

@dataclass
class StockData:
    symbol: str
    name: str
    change_pct: float
    sector: str
    concepts: List[str]
    # 外部数据缓存 (扫描/分组时填充)
    sector_change: float = 0.0
    concept_changes: Dict[str, float] = field(default_factory=dict)

@dataclass
class AnalysisTask:
    task_id: str
    task_type: str  # "SECTOR" (板块), "CONCEPT" (概念), "STOCK" (个股)
    target_name: str
    involved_stocks: List[str]  # 涉及的股票名称或代码列表

class Dispatcher:
    def __init__(self):
        self.stock_api = AkShareTool()
        self.sector_cache = {}
        self.concept_cache = {}

    def _get_sector_change_cached(self, sector_name: str) -> float:
        if not sector_name:
            return 0.0
        # 直接查缓存，如果没有则返回 0.0 (因为我们已经一次性获取了所有)
        return self.sector_cache.get(sector_name, 0.0)

    def _get_concept_change_cached(self, concept_name: str) -> float:
        if not concept_name:
            return 0.0
        return self.concept_cache.get(concept_name, 0.0)

    def scan(self, stock_codes: List[str]) -> List[StockData]:
        """
        Step 1: 量化扫描 (并发)
        优化后的流程 (批量获取模式):
        1. 批量获取所有行业板块和概念板块的涨跌幅数据 (Populate Cache)。
        2. 并行获取股票原始数据。
        3. 组装结果 (直接查缓存)。
        """
        # 阶段 0: 预热缓存 (批量获取)
        if not self.sector_cache:
            self.sector_cache = self.stock_api.get_all_sector_data()
        if not self.concept_cache:
            self.concept_cache = self.stock_api.get_all_concept_data()
            
        print(f"⚡ [Dispatcher] 已缓存 {len(self.sector_cache)} 个板块和 {len(self.concept_cache)} 个概念的数据。")

        # 阶段 1: 并行获取股票数据
        print(f"📡 [Dispatcher] 正在并行扫描 {len(stock_codes)} 只股票...")
        raw_data_list = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_code = {
                executor.submit(self.stock_api.get_stock_raw_data, code): code 
                for code in stock_codes
            }
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    data = future.result()
                    if data:
                        raw_data_list.append(data)
                        print(f"  > [成功] {data['name']} ({code})")
                    else:
                        print(f"  > [失败] {code}")
                except Exception as exc:
                    print(f"  > [错误] {code}: {exc}")

        # 阶段 2: 组装 (无需再次请求网络，直接使用缓存)
        results = []
        for raw in raw_data_list:
            stock_data = StockData(
                symbol=raw['symbol'],
                name=raw['name'],
                change_pct=raw['change_pct'],
                sector=raw['sector'],
                concepts=raw['concepts']
            )
            
            # 从缓存填充
            stock_data.sector_change = self._get_sector_change_cached(raw['sector'])
            
            for concept in raw['concepts']:
                stock_data.concept_changes[concept] = self._get_concept_change_cached(concept)
            
            results.append(stock_data)

        return results

    def classify_stock(self, stock: StockData) -> Tuple[str, str]:
        """
        Public helper to get the default classification for a stock.
        Returns: (task_type, target_name)
        """
        # 逻辑 1: 板块共振
        if abs(stock.change_pct - stock.sector_change) < 2.0:
            return ("SECTOR", stock.sector)

        # 逻辑 2: 概念跟风
        for concept, concept_change in stock.concept_changes.items():
            if abs(stock.change_pct - concept_change) < 3.0:
                return ("CONCEPT", concept)

        # 逻辑 3: 独立行情
        return ("STOCK", stock.name)

    def group_and_generate_tasks(self, data_list: List[StockData]) -> List[AnalysisTask]:
        """
        Step 2 & 3: 分组 & 归约
        对股票进行分类并生成合并后的任务。
        """
        # Buckets: Key = (Type, TargetName), Value = List[StockData]
        buckets: Dict[Tuple[str, str], List[StockData]] = {}
        
        print(f"⚖️ [Dispatcher] 正在对 {len(data_list)} 只股票进行分组...")

        for stock in data_list:
            task_type, target_name = self.classify_stock(stock)
            
            key = (task_type, target_name)
            if key not in buckets: buckets[key] = []
            buckets[key].append(stock)
            
            # Print log for debugging (consistent with previous behavior)
            if task_type == "SECTOR":
                print(f"  -> {stock.name} 归入板块共振 [{target_name}]")
            elif task_type == "CONCEPT":
                print(f"  -> {stock.name} 归入概念跟风 [{target_name}]")
            else:
                print(f"  -> {stock.name} 归入独立行情")

        return self._create_tasks_from_buckets(buckets)

    def generate_tasks_from_assignments(self, assignments: List[Tuple[StockData, str, str]]) -> List[AnalysisTask]:
        """
        Generates tasks from manual assignments.
        assignments: List of (StockData, task_type, target_name)
        """
        buckets: Dict[Tuple[str, str], List[StockData]] = {}
        
        for stock, task_type, target_name in assignments:
            key = (task_type, target_name)
            if key not in buckets: buckets[key] = []
            buckets[key].append(stock)
            
        return self._create_tasks_from_buckets(buckets)

    def _create_tasks_from_buckets(self, buckets: Dict[Tuple[str, str], List[StockData]]) -> List[AnalysisTask]:
        tasks = []
        task_counter = 1
        
        for (task_type, target_name), stocks in buckets.items():
            stock_names = [s.name for s in stocks]
            
            task = AnalysisTask(
                task_id=f"TASK_{task_counter:03d}",
                task_type=task_type,
                target_name=target_name,
                involved_stocks=stock_names
            )
            tasks.append(task)
            task_counter += 1
            
        print(f"✅ [Dispatcher] 已从 {sum(len(v) for v in buckets.values())} 只股票生成 {len(tasks)} 个任务。")
        return tasks

if __name__ == "__main__":
    # 简单测试运行
    dispatcher = Dispatcher()
    # 测试一些代码 (假设它们存在，例如 平安银行, 宁德时代)
    # 000001: 平安银行
    # 300750: 宁德时代
    # 600036: 招商银行
    test_codes = ["000001", "300750", "600036"] 
    data = dispatcher.scan(test_codes)
    tasks = dispatcher.group_and_generate_tasks(data)
    
    for t in tasks:
        print(f"Task: [{t.task_type}] {t.target_name} -> {t.involved_stocks}")
