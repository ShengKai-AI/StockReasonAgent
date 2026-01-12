import sys
import os
import argparse

# Add src to python path for local execution if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dispatcher import AnalysisTask
from src.graph.workflow import create_worker_graph

def run_integration_test():
    print("🚀 [Integration Test] Starting Layer 2 Workflow...")
    
    # 1. Create a Fake Task (Simulating Layer 1 Output)
    task = AnalysisTask(
        task_id="TEST_001",
        task_type="SECTOR",
        target_name="银行",
        involved_stocks=["招商银行", "平安银行", "兴业银行"]
    )
    
    # 2. Initialize Graph
    try:
        app = create_worker_graph()
    except Exception as e:
        print(f"❌ Failed to build graph: {e}")
        return

    # 3. Initial State
    initial_state = {
        "task": task,
        "search_query": None,
        "loop_count": 0
    }
    
    print(f"📥 Input Task: {task.target_name} ({task.task_type})")
    
    # 4. Run Graph
    try:
        final_state = app.invoke(initial_state)
        
        print("\n✅ Workflow Completed!")
        print("-" * 50)
        print(f"🎯 Confidence Score: {final_state.get('confidence_score')}")
        print(f"🔄 Loop Count: {final_state.get('loop_count')}")
        print("-" * 50)
        print("📄 Report Content:")
        print(final_state.get('report_content'))
        print("-" * 50)
        
    except Exception as e:
        print(f"❌ Workflow Execution Failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="StockReasonAgent CLI")
    parser.add_argument("--test", action="store_true", help="Run integration test for Layer 2")
    args = parser.parse_args()

    if args.test:
        run_integration_test()
    else:
        print("StockReasonAgent CLI")
        print("Usage: python src/main.py --test")

if __name__ == "__main__":
    main()
