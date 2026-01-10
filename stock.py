import akshare as ak
import pandas as pd
from datetime import datetime

class StockInfo:
    def __init__(self):
        print("📡 初始化 A股数据雷达 (Based on EastMoney)...")

    def _clean_symbol(self, symbol):
        """
        清洗代码格式：把 'SH600000' 转化为 '600000'
        因为东方财富接口通常只需要 6 位数字代码
        """
        return symbol.replace("SH", "").replace("SZ", "").replace("bj", "")

    def get_stock_realtime_data(self, symbol):
        """
        获取 实时行情 + 基础画像
        """
        clean_code = self._clean_symbol(symbol)
        
        try:
            # step 1: 获取实时行情 (这是为了拿到当天的涨跌幅、换手率)
            print(f"🔍 正在扫描市场数据: {clean_code}...")
            
            df_hist = ak.stock_zh_a_hist(
                symbol=clean_code, 
                period="daily", 
                start_date="20260101", 
                adjust="qfq"
            )
            
            if df_hist.empty:
                return f"❌ 未找到代码 {clean_code} 的数据"
            
            latest_data = df_hist.iloc[-1]

            # Step 2: 获取静态画像 (行业分类)
            info_df = ak.stock_individual_info_em(symbol=clean_code)
            info_dict = dict(zip(info_df['item'], info_df['value']))

            # Step 3: 组装成 Agent 易读的 Context
            agent_context = {
                "股票名称": info_dict.get('股票简称', 'Unknown'),
                "股票代码": symbol,
                "当前价格": latest_data['收盘'], # 盘中即为最新价
                "今日涨跌幅": f"{latest_data['涨跌幅']}%",
                "今日换手率": f"{latest_data['换手率']}%", 
                "成交量": f"{latest_data['成交量']} 手",
                "所属行业": info_dict.get('行业'),
                "总市值": f"{info_dict.get('总市值')} 元",
                "总市值": f"{info_dict.get('总市值')} 元",
                "数据日期": str(latest_data['日期']),
                "热门概念":  ", ".join(self.get_stock_concepts(symbol)) # 新增概念数据
            }
            
            return agent_context

        except Exception as e:
            return f"❌ 数据获取失败: {str(e)}"

    def get_market_context(self, stock_symbol, stock_info):
        """
        功能：获取板块数据并进行【异动判断】
        输入：stock_info (上一步获取的个股字典)
        输出：包含策略判断的完整 Context
        """
        industry_name = stock_info.get("所属行业")
        stock_change = float(stock_info.get("今日涨跌幅").replace("%", ""))
        
        print(f"📊 正在比对板块效应: {stock_symbol} ({industry_name}) vs 行业指数...")

        try:
            # 1. 获取所有行业板块的今日实时涨跌幅
            sector_df = ak.stock_board_industry_name_em()
            
            # 2. 找到对应的板块
            target_sector = sector_df[sector_df['板块名称'] == industry_name]
        
            sector_data = target_sector.iloc[0]
            sector_change = sector_data['涨跌幅']
            sector_name = sector_data['板块名称']

            # 3. ⚖️ 核心算法：计算偏离度
            divergence = stock_change - sector_change
            
            # 设定阈值 (Threshold)
            # 绝对差值小于 2.5%，我们认为它主要受板块带动
            is_resonance = abs(divergence) < 2.5 
            
            # 4. 生成 Agent 策略 (Strategy)
            if is_resonance:
                reasoning = "板块共振"
                search_strategy = f"重点搜索 '{sector_name}' 行业的近日政策、原材料价格或宏观消息，无需过度关注个股特定新闻。"
            else:
                reasoning = "独立行情"
                if divergence > 0:
                    status = "强势领涨"
                else:
                    status = "弱势领跌"
                search_strategy = f"该股走势与板块偏离 {divergence:.2f}% ({status})。必须重点搜索 '{stock_info['股票名称']}' 的个股公告、研报或传闻。"

            return {
                "板块名称": sector_name,
                "板块涨跌幅": f"{sector_change}%",
                "个股涨跌幅": f"{stock_change}%",
                "相对强弱": f"{divergence:.2f}%",
                "异动类型": reasoning,
                "搜索策略建议": search_strategy
            }

        except Exception as e:
            return {"Error": f"板块分析失败: {str(e)}"}

    def get_stock_concepts(self, stock_code):
        """
        功能：获取个股的热门概念关键词（取热度 Top 3）
        """
        try:
            df = ak.stock_hot_keyword_em(symbol=stock_code)
            if df.empty:
                return []
            
            ignore_list = [
                "长江三角", "珠江三角", "融资融券", "沪股通", "上证180", 
                "行业龙头", "标准普尔", "富时罗素", "证金持股"
            ]
            
            # 按热度降序排列，取前3个概念名称
            df = df.sort_values(by='热度', ascending=False)
            concepts = df['概念名称'].head(3).tolist()
            
            # 过滤掉 ignore_list 中的概念
            concepts = [concept for concept in concepts if concept not in ignore_list]
            
            return concepts
        except Exception as e:
            print(f"⚠️ 概念数据获取失败: {e}")
            return []

# --- 运行测试 ---
stock = StockInfo()

# 测试 1: 浦发银行 (SH600000)
# 你可以直接输 600000 或 SH600000，代码里做了兼容
print("\n------- 测试结果 -------")
stock_code = "SH600000"
stock_data = stock.get_stock_realtime_data(stock_code)

if isinstance(stock_data, dict):
    # 2. 进行板块比对
    analysis = stock.get_market_context(stock_code, stock_data)
    
    # 3. 合并结果，准备发给 LLM
    final_context = {**stock_data, **analysis}
    
    import json
    print(json.dumps(final_context, indent=4, ensure_ascii=False))
else:
    print(stock_data)