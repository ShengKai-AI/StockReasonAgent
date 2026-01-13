from tavily import TavilyClient
import streamlit as st
import os

def get_tavily_api_key():
    if "TAVILY_API_KEY" in st.secrets:
        return st.secrets["TAVILY_API_KEY"]
    return os.getenv("TAVILY_API_KEY")

class TavilySearchTool:
    def __init__(self):
        self.client = None

    def _ensure_client(self):
        if self.client:
            return True
            
        api_key = get_tavily_api_key()
        if not api_key:
            return False
            
        try:
            self.client = TavilyClient(api_key=api_key)
            return True
        except Exception as e:
            print(f"⚠️ 初始化 Tavily Client 失败: {e}")
            return False

    def search(self, query: str) -> list:
        """
        执行搜索并返回结构化结果列表。
        Returns: List[Dict] usually containing 'title', 'url', 'content'.
        """
        if not self._ensure_client():
            return [{"title": "Error", "url": "#", "content": "未配置 Tavily API Key。"}]
            
        print(f"🕵️‍♂️ [Layer 2] 正在调用 Tavily 搜索: {query}")
        try:
            target_domains = [
                "cls.cn", "eastmoney.com", "stcn.com", 
                "10jqka.com.cn", "sina.com.cn", "hexun.com",
                "gelonghui.com", "caixin.com"
            ]

            response = self.client.search(
                query=query,
                search_depth="advanced", 
                topic="news",          
                time_range="week",
                include_domains=target_domains, 
                max_results=7,
                include_raw_content=False
            )
            
            valid_results = []
            if 'results' in response and len(response['results']) > 0:
                for item in response['results']:
                    # 简单的长度过滤
                    if len(item.get('content', '')) > 20: 
                        valid_results.append({
                            "title": item['title'],
                            "url": item['url'],
                            "content": item['content']
                        })
            
            return valid_results

        except Exception as e:
            return [{"title": "Error", "url": "#", "content": f"搜索错误: {str(e)}"}]

# Global instance
search_tool = TavilySearchTool()

def run_search(query: str) -> list:
    return search_tool.search(query)
