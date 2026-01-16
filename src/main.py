import sys
import os
import argparse
import toml

# 如果需要本地执行，添加 src 到 python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 secrets
def load_secrets():
    secrets_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".streamlit/secrets.toml")
    if os.path.exists(secrets_path):
        try:
            secrets = toml.load(secrets_path)
            # 加载顶级 key
            for k, v in secrets.items():
                if isinstance(v, str):
                    os.environ[k] = v
            # 加载 general section
            if "general" in secrets:
                for k, v in secrets["general"].items():
                    os.environ[k] = v
        except Exception as e:
            print(f"⚠️ Warning: Failed to load secrets: {e}")

load_secrets()

from src.dispatcher import AnalysisTask
from src.graph.workflow import create_worker_graph

def run_integration_test():
    print("🚀 [集成测试] 开始 Layer 2 工作流...")
    
    # 1. 创建一个伪造任务 (模拟 Layer 1 输出)
    task = AnalysisTask(
        task_id="TEST_001",
        task_type="SECTOR",
        target_name="银行",
        involved_stocks=["招商银行", "平安银行", "兴业银行"]
    )
    
    # 2. 初始化图
    try:
        app = create_worker_graph()
    except Exception as e:
        print(f"❌ 构建图失败: {e}")
        return

    # 3. 初始状态
    initial_state = {
        "task": task,
        "search_query": None,
        "loop_count": 0
    }
    
    print(f"📥 输入任务: {task.target_name} ({task.task_type})")
    
    # 4. 运行图
    try:
        final_state = app.invoke(initial_state)
        
        print("\n✅ 工作流完成!")
        print("-" * 50)
        print(f"🎯 置信度得分: {final_state.get('confidence_score')}")
        print(f"🔄 循环次数: {final_state.get('loop_count')}")
        print("-" * 50)
        print("📄 报告内容:")
        print(final_state.get('report_content'))
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="StockReasonAgent CLI 工具")
    parser.add_argument("--test", action="store_true", help="运行 Layer 2 集成测试")
    args = parser.parse_args()

    if args.test:
        run_integration_test()
    else:
        print("StockReasonAgent CLI (命令行工具)")
        print("用法: python src/main.py --test")

if __name__ == "__main__":
    main()
