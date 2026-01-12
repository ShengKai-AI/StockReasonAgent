import streamlit as st
import pandas as pd
import time
from typing import List, Dict

# 确保路径正确
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.dispatcher import Dispatcher, StockData, AnalysisTask
from src.graph.workflow import create_worker_graph
# Import from root auth_manager
from auth_manager import init_auth, login_widget, logout_widget

# 初始化 Auth
authenticator = init_auth()

def init_session_state():
    if 'dispatcher' not in st.session_state:
        st.session_state['dispatcher'] = Dispatcher()
    if 'worker_app' not in st.session_state:
         try:
            st.session_state['worker_app'] = create_worker_graph()
         except Exception as e:
            st.error(f"Failed to initialize Worker Graph: {e}")
            
    # Workflow Steps
    if 'step' not in st.session_state:
        st.session_state['step'] = 1  # 1: Input, 2: Review/Classify, 3: Tasks Preview, 4: Execution/Report
        
    # Data Storage
    if 'stock_data_list' not in st.session_state:
        st.session_state['stock_data_list'] = [] # List[StockData]
    if 'manual_assignments' not in st.session_state:
        st.session_state['manual_assignments'] = [] # List[Dict] for editing
    if 'generated_tasks' not in st.session_state:
        st.session_state['generated_tasks'] = [] # List[AnalysisTask]
    if 'task_results' not in st.session_state:
        st.session_state['task_results'] = {} # task_id -> {status, score, report, reflection}

def render_step_1_input():
    st.header("Step 1: 批量输入股票")
    
    default_text = "600036, 000001, 300750"
    user_input = st.text_area("请输入股票代码 (逗号或换行分隔)", value=default_text, height=150)
    
    if st.button("开始扫描 (Scan)"):
        # Parse input
        codes = [c.strip() for c in user_input.replace("\n", ",").split(",") if c.strip()]
        
        if not codes:
            st.warning("请输入至少一个股票代码")
            return

        with st.spinner("正在扫描市场数据... (可能需要几秒钟)"):
            data_list = st.session_state['dispatcher'].scan(codes)
            st.session_state['stock_data_list'] = data_list
            
            # Pre-calculate default assignments for Step 2
            assignments = []
            for stock in data_list:
                t_type, t_target = st.session_state['dispatcher'].classify_stock(stock)
                assignments.append({
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "change": stock.change_pct,
                    "sector_change": stock.sector_change,
                    "task_type": t_type,
                    "target_name": t_target,
                    "original_stock": stock # Keep reference
                })
            st.session_state['manual_assignments'] = assignments
            
            st.session_state['step'] = 2
            st.rerun()

def render_step_2_classify():
    st.header("Step 2: 异动分类与调整")
    st.info("请审查下方的自动分类结果。您可以手动修改归因类型和目标，以纠正逻辑。")
    
    assignments = st.session_state['manual_assignments']
    
    # We use a cleaner UI than st.data_editor because we want specific dropdowns, 
    # but st.data_editor is more compact. Let's try st.data_editor for compactness if possible,
    # or a loop of columns for flexibility. 
    # Since we need to modify 'task_type' (Dropdown) and 'target_name' (Text), st.data_editor is tricky for mixed customization 
    # without defining a ColumnConfig.
    
    # Prepare DataFrame for Display
    df_data = []
    
    # Map for dropdown options
    TYPE_OPTIONS = ["SECTOR", "CONCEPT", "STOCK"]
    
    # We will loop to render rows for better control
    updated_assignments = []
    
    st.markdown("### 分类调整表")
    
    # Table Header
    cols = st.columns([1.5, 1, 1, 1.5, 2, 2])
    cols[0].markdown("**股票**")
    cols[1].markdown("**涨跌幅**")
    cols[2].markdown("**板块涨幅**")
    cols[3].markdown("**热门概念**")
    cols[4].markdown("**归因类型**")
    cols[5].markdown("**归因目标**")
    
    for idx, item in enumerate(assignments):
        with st.container():
            cols = st.columns([1.5, 1, 1, 1.5, 2, 2])
            
            # Static Info
            cols[0].write(f"{item['name']} ({item['symbol']})")
            
            change_color = "red" if item['change'] > 0 else "green"
            cols[1].markdown(f":{change_color}[{item['change']}%]")
            
            cols[2].write(f"{item['sector_change']}%")
            
            concepts_str = ", ".join(item['original_stock'].concepts[:2])
            cols[3].caption(concepts_str)
            
            # Interactive Controls
            new_type = cols[4].selectbox(
                "Type", 
                TYPE_OPTIONS, 
                index=TYPE_OPTIONS.index(item['task_type']), 
                key=f"type_{idx}",
                label_visibility="collapsed"
            )
            
            new_target = cols[5].text_input(
                "Target", 
                value=item['target_name'], 
                key=f"target_{idx}",
                label_visibility="collapsed"
            )
            
            # Update item (create localized copy to avoid mutating session state directly in loop issue?)
            # Actually we can just update the list after loop or update dict in place
            item['task_type'] = new_type
            item['target_name'] = new_target
            updated_assignments.append(item)
            
    st.session_state['manual_assignments'] = updated_assignments

    st.divider()
    
    col_back, col_next = st.columns([1, 1])
    if col_back.button("🔙 返回重新扫描"):
        st.session_state['step'] = 1
        st.rerun()
        
    if col_next.button("✅ 确认并生成任务"):
        # Generate tasks based on UI inputs
        assigned_tuples = [
            (a['original_stock'], a['task_type'], a['target_name']) 
            for a in st.session_state['manual_assignments']
        ]
        
        tasks = st.session_state['dispatcher'].generate_tasks_from_assignments(assigned_tuples)
        st.session_state['generated_tasks'] = tasks
        st.session_state['task_results'] = {} # Reset results if we regenerate tasks
        
        st.session_state['step'] = 3
        st.rerun()

def render_step_3_preview():
    st.header("Step 3: 任务预览")
    tasks = st.session_state['generated_tasks']
    
    if not tasks:
        st.warning("未生成任何任务。请返回检查分类。")
        if st.button("返回"):
            st.session_state['step'] = 2
            st.rerun()
        return

    st.write(f"共生成 **{len(tasks)}** 个分析任务。请确认后开始执行。")
    
    # Task Selection (Optional, for now assume all)
    # We can add checkboxes if needed.
    
    for t in tasks:
        with st.expander(f"📌 [{t.task_type}] {t.target_name} ({len(t.involved_stocks)} 股)"):
            st.write(f"**涉及股票**: {', '.join(t.involved_stocks)}")
            st.write(f"**任务ID**: {t.task_id}")

    col_back, col_run = st.columns([1, 1])
    if col_back.button("🔙 返回调整分类"):
        st.session_state['step'] = 2
        st.rerun()
        
    if col_run.button("🚀 开始执行分析 (Start Analysis)"):
        st.session_state['step'] = 4
        # Initializing result placeholders
        for t in tasks:
            st.session_state['task_results'][t.task_id] = {
                "status": "pending", # pending, running, success, fail
                "score": 0.0,
                "report": "",
                "reflection": "",
                "task_obj": t
            }
        st.rerun()

def render_step_4_execution():
    st.header("Step 4: 执行与报告看板")
    
    tasks = st.session_state['generated_tasks']
    results = st.session_state['task_results']
    app = st.session_state['worker_app']
    
    # Progress Bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Run Logic (Only if any task is pending)
    pending_tasks = [t for t in tasks if results[t.task_id]['status'] == 'pending']
    
    if pending_tasks:
        total = len(tasks)
        completed = len(tasks) - len(pending_tasks)
        
        for i, task in enumerate(pending_tasks):
            current_idx = completed + i + 1
            progress_bar.progress(current_idx / total)
            status_text.markdown(f"🔄 正在分析: **[{task.task_type}] {task.target_name}** ({current_idx}/{total})...")
            
            # --- LangGraph Execution ---
            results[task.task_id]['status'] = 'running'
            
            try:
                initial_state = {
                    "task": task,
                    "search_query": None,
                    "loop_count": 0
                }
                final_state = app.invoke(initial_state)
                
                # Update Result
                score = final_state.get('confidence_score', 0.0)
                results[task.task_id]['score'] = score
                results[task.task_id]['report'] = final_state.get('report_content', 'No Content')
                results[task.task_id]['reflection'] = final_state.get('reflection', '')
                
                # Determine Success based on score
                if score > 0.6:
                    results[task.task_id]['status'] = 'success'
                else:
                    results[task.task_id]['status'] = 'fail_low_score'
            
            except Exception as e:
                results[task.task_id]['status'] = 'error'
                results[task.task_id]['report'] = f"Error: {e}"
            
            # Force UI update somewhat? Streamlit updates on rerun mostly.
            # We can't easily do partial updates without rerun in loop or st.empty() tricks.
            # But the results dict is updated.
            
        status_text.success("✅ 所有任务分析完成！")
        progress_bar.progress(1.0)
        st.rerun() # Refresh to show final state

    # --- Dashboard View ---
    
    st.subheader("📊 状态看板")
    
    # Create a grid of cards
    cols = st.columns(3)
    
    for idx, task in enumerate(tasks):
        res = results[task.task_id]
        status = res['status']
        col = cols[idx % 3]
        
        # Color coding
        if status == 'success':
            border_color = "gainsboro" # Streamlit doesn't support custom border color easily in native cards
            emoji = "🟢"
            bg_color = "#e6fffa" # Light green hint (custom css needed for true bg)
        elif status == 'fail_low_score':
            emoji = "🔴"
        elif status == 'error':
            emoji = "⚠️"
        else: # pending/running
            emoji = "⏳"
        
        with col:
            with st.container(border=True):
                st.markdown(f"### {emoji} {task.target_name}")
                st.caption(f"Type: {task.task_type} | Stocks: {len(task.involved_stocks)}")
                if status == 'success':
                    st.markdown(f"**Score: {res['score']}**")
                elif status == 'fail_low_score':
                    st.markdown(f":red[Score: {res['score']}]")
                elif status == 'error':
                    st.markdown(":red[Error]")
                
                # Button to open report editor
                if st.button(f"查看/编辑报告", key=f"btn_{task.task_id}"):
                     view_report_dialog(task.task_id)

    if st.button("🔙 返回任务列表"):
        st.session_state['step'] = 3
        st.rerun()

@st.dialog("归因报告编辑器", width="large")
def view_report_dialog(task_id):
    res = st.session_state['task_results'][task_id]
    task = res['task_obj']
    
    st.markdown(f"### {task.target_name} ({task.task_type})")
    
    # Reflection / Status Info
    if res['status'] == 'fail_low_score':
        st.error(f"⚠️ 置信度低 ({res['score']})。请参考反思并手动补充报告。")
        with st.expander("查看 AI 反思 (Reflection)"):
            st.write(res['reflection'])
    elif res['status'] == 'success':
        st.success(f"✅ 置信度合格 ({res['score']})")
    
    # Editor
    new_report = st.text_area("Report Content (Markdown)", value=res['report'], height=400)
    
    if st.button("保存修改"):
        res['report'] = new_report
        st.session_state['task_results'][task_id] = res
        st.success("已保存！")
        st.rerun()

def main():
    st.set_page_config(page_title="StockReasonAgent", layout="wide")
    
    # Auth Logic
    login_widget(authenticator)
    
    if st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
        return
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your username and password')
        return
        
    # Authenticated
    with st.sidebar:
        st.title("StockReasonAgent")
        st.write(f"User: *{st.session_state['name']}*")
        logout_widget(authenticator)

    # Init
    init_session_state()
    
    step = st.session_state['step']
    
    # Progress Stepper
    st.markdown(
        """
        <style>
        .step { font-weight: bold; padding: 5px; border-radius: 5px; }
        .active { background-color: #f0f2f6; color: #31333F; }
        </style>
        """, unsafe_allow_html=True
    )
    
    step_cols = st.columns(4)
    step_names = ["1. 输入", "2. 分类调整", "3. 任务预览", "4. 执行报告"]
    for i, name in enumerate(step_names):
        s_num = i + 1
        decoded_name = name
        if s_num == step:
            step_cols[i].markdown(f"**🔹 {decoded_name}**")
        else:
            step_cols[i].markdown(f"{decoded_name}")
            
    st.divider()

    # Render Active Step
    if step == 1:
        render_step_1_input()
    elif step == 2:
        render_step_2_classify()
    elif step == 3:
        render_step_3_preview()
    elif step == 4:
        render_step_4_execution()

if __name__ == "__main__":
    main()
