import requests
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any, Optional

class NewsScore(BaseModel):
    relevance: float = Field(..., description="Relevance score (0-1)")
    sentiment: str = Field(default="中性", description="Sentiment")
    reason: str = Field(default="No reason provided", description="Short reasoning")
    
    # 增加一个 computed field 或者 alias 兼容 logic
    @property
    def score(self) -> float:
        return self.relevance

class SmallModelClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.model = "finance-expert"

    def analyze(self, news_content: str, target_name: str) -> Dict[str, Any]:
        """
        调用本地小模型对单条新闻进行评分。
        """
        instruction = f"分析此消息对【{target_name}】的影响。直接输出JSON。"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": f"### Instruction:\n{instruction}\n### Input:\n{news_content[:2000]}\n\n### Response:"} # 截断防止过长
            ],
            "format": "json",
            "stream": False,
            "options": {
                "num_ctx": 1024,  # 上下文：从默认值砍到 1024 甚至 512
            }
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result['message']['content']
            
            # 使用 Pydantic 解析和验证
            score_data = NewsScore.model_validate_json(content)
            # 转为 dict，并手动注入 'score' 以兼容上层代码
            result_dict = score_data.model_dump()
            result_dict['score'] = score_data.score
            return result_dict
            
        except ValidationError as e:
            print(f"❌ [Small Model] Validation Error: {e}")
            return {"score": 0, "reason": "Format Error"}
        except Exception as e:
            print(f"❌ [Small Model] Error: {e}")
            return {"score": 0, "reason": f"Error: {str(e)}"}
