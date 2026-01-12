from tavily import TavilyClient
import streamlit as st
import os

def get_tavily_api_key():
    if "TAVILY_API_KEY" in st.secrets:
        return st.secrets["TAVILY_API_KEY"]
    return os.getenv("TAVILY_API_KEY")

class TavilySearchTool:
    def __init__(self):
        self.api_key = get_tavily_api_key()
        if not self.api_key:
            print("⚠️ 警告: 未找到 TAVILY_API_KEY。")
        else:
            self.client = TavilyClient(api_key=self.api_key)

    def search(self, query: str) -> str:
        """
        执行搜索并返回格式化的摘要。
        """
        if not self.api_key:
            return "错误: 未配置 Tavily API Key。"
            
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
            
            summary_lines = []
            if 'results' in response and len(response['results']) > 0:
                for item in response['results']:
                    # 简单的长度过滤
                    if len(item.get('content', '')) > 20: 
                        line = f"- [{item['title']}]({item['url']}): {item['content'][:300]}..."
                        summary_lines.append(line)
            
            if not summary_lines:
                return "未通过搜索找到相关的高质量新闻。"
                
            return "\n\n".join(summary_lines)

        except Exception as e:
            return f"搜索错误: {str(e)}"

# Global instance
search_tool = TavilySearchTool()

def run_search(query: str) -> str:
    return search_tool.search(query)
