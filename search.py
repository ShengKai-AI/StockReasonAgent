from tavily import TavilyClient
import datetime

class NewsSearch:
    def __init__(self, api_key):
        self.client = TavilyClient(api_key=api_key)
        
    def search_attribution_news(self, query):
        """
        执行搜索并返回结构化数据
        输入：
        - query: 用户确认过的最终搜索词
        """
        print(f"🕵️‍♂️ 执行搜索: [{query}] ...")

        try:
            # 制定搜索源
            target_domains = [
                "cls.cn",           # 财联社
                "eastmoney.com",    # 东方财富
                "stcn.com",         # 证券时报
                "10jqka.com.cn",    # 同花顺
                "sina.com.cn",      # 新浪财经
                "hexun.com"         # 和讯网
            ]

            response = self.client.search(
                query=query,
                search_depth="advanced", 
                topic="news",          
                time_range="week",
                include_domains=target_domains, 
                max_results=10, # 稍微多抓一点供用户筛选
                include_raw_content=False
            )
            
            # 数据清洗与结构化
            cleaned_results = []
            if 'results' in response and len(response['results']) > 0:
                for item in response['results']:
                    # 过滤掉内容太短的无效信息
                    if len(item.get('content', '')) > 10: 
                        cleaned_results.append({
                            "title": item['title'],
                            "url": item['url'],
                            "content": item['content'],
                            "published_date": item.get('published_date', 'Unknown')
                        })
                return {"results": cleaned_results}
            else:
                return {"results": []}

        except Exception as e:
            # 返回错误结构，方便 UI 处理
            return {"error": str(e), "results": []}

# --- 测试代码 ---
if __name__ == "__main__":
    import os
    # 请确保环境变量中有 TAVILY_API_KEY，或在此处临时替换
    key = os.getenv("TAVILY_API_KEY", "your_api_key_here") 
    search = NewsSearch(key)
    # res = search.search_attribution_news("浦发银行 股价异动") # 注释掉执行，避免报错
    # print(res)