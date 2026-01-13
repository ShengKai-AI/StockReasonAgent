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
# 从根目录导入 auth_manager
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
            st.error(f"初始化 Worker Graph 失败: {e}")
            
    # 工作流步骤
    if 'step' not in st.session_state:
        st.session_state['step'] = 1  # 1: 输入, 2: 审查/分类, 3: 任务预览, 4: 执行/报告
        
    # 数据存储
    if 'stock_data_list' not in st.session_state:
        st.session_state['stock_data_list'] = [] # List[StockData]
    if 'manual_assignments' not in st.session_state:
        st.session_state['manual_assignments'] = [] # List[Dict] 用于编辑
    if 'generated_tasks' not in st.session_state:
        st.session_state['generated_tasks'] = [] # List[AnalysisTask]
    if 'task_results' not in st.session_state:
        st.session_state['task_results'] = {} # task_id -> {status, score, report, reflection}
    if 'execution_logs' not in st.session_state:
        st.session_state['execution_logs'] = {} # task_id -> 列表，存储执行过程中的日志条目
        
    # 预热缓存 (只运行一次，后台线程)
    if 'cache_warmed_up' not in st.session_state:
        # 调用 Dispatcher 的异步预热方法
        st.session_state['dispatcher'].start_async_warmup()
        st.session_state['cache_warmed_up'] = True

def render_step_1_input():
    st.header("Step 1: 批量输入股票")
    
    default_text = "600036, 000001, 300750"
    user_input = st.text_area("请输入股票代码 (逗号或换行分隔)", value=default_text, height=150)
    
    if st.button("开始扫描", type="primary"):
        # 解析输入
        codes = [c.strip() for c in user_input.replace("\n", ",").split(",") if c.strip()]
        
        if not codes:
            st.warning("请输入至少一个股票代码")
            return

        with st.spinner("正在扫描市场数据... (可能需要几秒钟)"):
            data_list = st.session_state['dispatcher'].scan(codes)
            st.session_state['stock_data_list'] = data_list
            
            # 预计算 Step 2 的默认分配
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
                    "original_stock": stock # 保持引用
                })
            st.session_state['manual_assignments'] = assignments
            
            st.session_state['step'] = 2
            st.rerun()

def render_step_2_classify():
    st.header("Step 2: 异动分类与调整")
    st.info("请审查下方的自动分类结果。您可以手动修改归因类型和目标，以纠正逻辑。")
    
    assignments = st.session_state['manual_assignments']
    
    # 映射字典 (Backend -> Display)
    TYPE_MAP = {
        "SECTOR": "板块共振",
        "CONCEPT": "概念带动",
        "STOCK": "个股行情"
    }
    # Display -> Backend
    REVERSE_TYPE_MAP = {v: k for k, v in TYPE_MAP.items()}
    DISPLAY_OPTIONS = list(TYPE_MAP.values())

    # 准备显示数据
    st.markdown("### 分类调整表")
    
    # 表头 (增加一列用于操作)
    cols = st.columns([1.5, 1, 1, 1.5, 1.5, 2, 0.5, 0.5])
    cols[0].markdown("**股票**")
    cols[1].markdown("**涨跌幅**")
    cols[2].markdown("**板块**")
    cols[3].markdown("**概念**")
    cols[4].markdown("**归因类型**")
    cols[5].markdown("**归因目标**")
    cols[6].markdown("") # 删除按钮
    cols[7].markdown("") # 增加按钮占位
    
    indices_to_remove = []
    
    for idx, item in enumerate(assignments):
        with st.container():
            cols = st.columns([1.5, 1, 1, 1.5, 1.5, 2, 0.5, 0.5])
            
            # 静态信息
            cols[0].write(f"{item['name']} ({item['symbol']})")
            
            # 处理新增股票可能没有 change 数据的情况
            change = item.get('change', 0.0)
            change_color = "red" if change > 0 else "green"
            cols[1].markdown(f":{change_color}[{change}%]")
            
            # 板块
            s_change = item.get('sector_change', 0.0)
            sector_color = "red" if s_change > 0 else "green"
            cols[2].markdown(f":{sector_color}[{s_change}%]")
            
            # 概念显示 (带涨跌幅)
            concepts = item.get('original_stock', None)
            if concepts:
                # 获取该股票所有的概念涨幅
                # 优先显示涨幅接近股票涨幅的，或者涨幅绝对值大的
                c_details = []
                for c_name, c_chg in concepts.concept_changes.items():
                    c_color = "red" if c_chg > 0 else "green"
                    c_details.append(f"{c_name} (:{c_color}[{c_chg}%])")
                
                # 只显示前 3 个，避免太长
                concepts_str = ", ".join(c_details[:3])
                if len(c_details) > 3:
                     concepts_str += "..."
                cols[3].markdown(concepts_str, help="\n".join(c_details))
            else:
                cols[3].write("")
            
            # 交互控件 - 类型 (中文)
            current_type_backend = item.get('task_type', 'STOCK')
            current_type_display = TYPE_MAP.get(current_type_backend, "个股行情")
            
            new_type_display = cols[4].selectbox(
                "Type", 
                DISPLAY_OPTIONS, 
                index=DISPLAY_OPTIONS.index(current_type_display) if current_type_display in DISPLAY_OPTIONS else 2, 
                key=f"type_{idx}",
                label_visibility="collapsed"
            )
            
            # 更新 Back-end type
            item['task_type'] = REVERSE_TYPE_MAP[new_type_display]

            # 归因目标
            new_target = cols[5].text_input(
                "Target", 
                value=item['target_name'], 
                key=f"target_{idx}",
                label_visibility="collapsed"
            )
            item['target_name'] = new_target
            
            # 删除按钮 (-)
            if cols[6].button("➖", key=f"del_{idx}"):
                indices_to_remove.append(idx)

    # 执行删除 (倒序删除以防索引偏移)
    if indices_to_remove:
        for i in sorted(indices_to_remove, reverse=True):
            del assignments[i]
        st.session_state['manual_assignments'] = assignments
        st.rerun()

    # 新增股票区域
    st.markdown("---")
    st.markdown("#### 补充股票")
    
    if 'temp_new_codes' not in st.session_state:
        st.session_state['temp_new_codes'] = ""
        
    col_add_input, col_add_btn = st.columns([4, 1], vertical_alignment="bottom")
    
    new_codes_input = col_add_input.text_input(
        " ", 
        value=st.session_state['temp_new_codes'],
        placeholder="例如: 601398, 000002"
    )
    st.session_state['temp_new_codes'] = new_codes_input
    
    if col_add_btn.button("扫描并添加", type="primary"):
        if new_codes_input:
            # 基础解析
            raw_codes = [c.strip() for c in new_codes_input.replace("，", ",").split(",") if c.strip()]
            
            # --- 去重逻辑 ---
            existing_symbols = {item['symbol'] for item in assignments}
            # 注意: 这里简单假设用户输入的代码可能包含后缀也可能不含，
            # 为了更严谨，我们应该先获取 stock_data 再去重，或者先简单过滤。
            # Dispatcher.scan 会处理后缀，所以我们这里先不做太严格的字符串去重，
            # 而是扫描后检查是否已存在于列表中。
            
            with st.spinner(f"正在扫描补录股票..."):
                new_data_candidates = st.session_state['dispatcher'].scan(raw_codes)
                
                added_count = 0
                duplicate_count = 0
                
                for stock in new_data_candidates:
                    if stock.symbol in existing_symbols:
                        duplicate_count += 1
                        continue # Skip existing
                        
                    # Add new
                    t_type, t_target = st.session_state['dispatcher'].classify_stock(stock)
                    assignments.append({
                        "symbol": stock.symbol,
                        "name": stock.name,
                        "change": stock.change_pct,
                        "sector_change": stock.sector_change,
                        "task_type": t_type,
                        "target_name": t_target,
                        "original_stock": stock 
                    })
                    existing_symbols.add(stock.symbol)
                    added_count += 1
                
                st.session_state['manual_assignments'] = assignments
                st.session_state['temp_new_codes'] = "" # Clear input
                
                if duplicate_count > 0:
                     st.warning(f"已忽略 {duplicate_count} 只重复股票，成功添加 {added_count} 只。")
                elif added_count > 0:
                     st.success(f"已添加 {added_count} 只股票")
                else:
                     st.warning("未找到有效股票或全部重复。")
                     
                st.rerun()

    st.divider()
    
    col_next, col_back, _ = st.columns([1, 1, 6]) 
    if col_next.button("确认并生成任务", type="primary"):
        # 基于 UI 输入生成任务
        assigned_tuples = [
            (a['original_stock'], a['task_type'], a['target_name']) 
            for a in st.session_state['manual_assignments']
        ]
        
        tasks = st.session_state['dispatcher'].generate_tasks_from_assignments(assigned_tuples)
        st.session_state['generated_tasks'] = tasks
        st.session_state['task_results'] = {} # 如果重新生成任务，重置结果
        
        st.session_state['step'] = 3
        st.rerun()

    if col_back.button("返回"):
        st.session_state['step'] = 1
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

    st.write(f"共生成 **{len(tasks)}** 个分析任务。请选择需要执行的任务：")
    
    selected_tasks = []
    
    TYPE_MAP = {
        "SECTOR": "板块共振",
        "CONCEPT": "概念带动",
        "STOCK": "个股行情"
    }

    for t in tasks:
        col_chk, col_det = st.columns([0.05, 0.95])
        with col_chk:
            # 默认全选
            is_selected = st.checkbox("选择", value=True, key=f"sel_{t.task_id}", label_visibility="collapsed")
        
        with col_det:
            # 使用中文类型显示
            display_type = TYPE_MAP.get(t.task_type, t.task_type)
            with st.expander(f"📌 [{display_type}] {t.target_name} ({len(t.involved_stocks)} 股)"):
                st.write(f"**涉及股票**: {', '.join(t.involved_stocks)}")
                st.write(f"**任务ID**: {t.task_id}")
        
        if is_selected:
            selected_tasks.append(t)

    col_run, col_back, _ = st.columns([1, 1, 6]) 
    if col_back.button("返回"):
        st.session_state['step'] = 2
        st.rerun()
        
    if col_run.button("开始执行任务", type="primary"):
        if not selected_tasks:
            st.warning("请至少选择一个任务！")
            return

        st.session_state['step'] = 4
        st.session_state['tasks_to_run'] = selected_tasks
        
        # 初始化结果占位符 (只为选中的任务)
        for t in selected_tasks:
            st.session_state['task_results'][t.task_id] = {
                "status": "pending", # pending, running, success, fail
                "score": 0.0,
                "report": "",
                "reflection": "",
                "search_results": "",
                "task_obj": t
            }
        st.rerun()

def render_step_4_execution():
    st.header("Step 4: 执行与报告看板")
    
    # 优先使用用户选择的任务列表
    tasks = st.session_state.get('tasks_to_run', st.session_state['generated_tasks'])
    results = st.session_state['task_results']
    app = st.session_state['worker_app']
    
    # 进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 执行逻辑 (如果有挂起的任务)
    pending_tasks = [t for t in tasks if results[t.task_id]['status'] == 'pending']
    
    if pending_tasks:
        total = len(tasks)
        completed = len(tasks) - len(pending_tasks)
        
        for i, task in enumerate(pending_tasks):
            current_idx = completed + i + 1
            progress_bar.progress(current_idx / total)
            # --- LangGraph 执行 ---
            results[task.task_id]['status'] = 'running'
            
            # 使用 st.status 提供可折叠的实时进度展示
            cn_type = {"SECTOR": "板块共振", "CONCEPT": "概念带动", "STOCK": "个股行情"}.get(task.task_type, task.task_type)
            
            with st.status(f"🤖 正在分析: [{cn_type}] {task.target_name}...", expanded=True) as status_container:
                
                # 获取或初始化该任务的持久化日志
                if task.task_id not in st.session_state['execution_logs']:
                    st.session_state['execution_logs'][task.task_id] = []
                task_logs = st.session_state['execution_logs'][task.task_id]
                
                # 1. 先渲染历史日志 (防止刷新后消失)
                for log_item in task_logs:
                    if log_item['type'] == 'search':
                        with st.expander(f"搜索结果 (Search Results)", expanded=True):
                            st.caption("Agent 实时搜索到的原始资讯：")
                            news = log_item['data']
                            if isinstance(news, list):
                                for item in news:
                                    icon = f"https://www.google.com/s2/favicons?domain={item.get('url', '')}"
                                    st.markdown(f"![icon]({icon}) [{item.get('title', 'No Title')}]({item.get('url', '#')})")
                            else:
                                st.markdown(str(news))
                    elif log_item['type'] == 'evaluate':
                        score = log_item['score']
                        reflect = log_item['reflection']
                        with st.expander(f"模型思考 (置信度: {score})", expanded=True):
                            st.write(reflect)
                    elif log_item['type'] == 'optimize':
                        st.write(f"优化搜索词: **{log_item['query']}**")

                initial_state = {
                    "task": task,
                    "search_query": None,
                    "loop_count": 0
                }
                
                final_state = initial_state.copy() # Local accumulator
                
                try:
                    # 使用 stream 获取中间步骤，实现流式展示
                    # 增加 recursion_limit 以防止多次循环导致被提前终止
                    stream_config = {"recursion_limit": 50}
                    for step_output in app.stream(initial_state, config=stream_config):
                        # step_output 格式: {'node_name': {updated_keys...}}
                        for node_name, updates in step_output.items():
                            if updates:
                                final_state.update(updates)
                            
                            # 2. 实时处理新日志并持久化
                            if node_name == 'search':
                                news = updates.get('search_results', [])
                                # 存入日志
                                log_entry = {'type': 'search', 'data': news}
                                task_logs.append(log_entry)
                                
                                # 立即渲染
                                with st.expander(f"🌍 搜索结果 (Search Results)", expanded=True):
                                    st.caption("Agent 实时搜索到的原始资讯：")
                                    if isinstance(news, list):
                                        for item in news:
                                            # 使用 Google Favicon API 获取图标
                                            icon = f"https://www.google.com/s2/favicons?domain={item.get('url', '')}"
                                            st.markdown(f"![icon]({icon}) [{item.get('title', 'No Title')}]({item.get('url', '#')})")
                                    else:
                                        st.markdown(str(news))
                                    
                            elif node_name == 'evaluate':
                                score = updates.get('confidence_score', 0)
                                reflect = updates.get('reflection', '')
                                log_entry = {'type': 'evaluate', 'score': score, 'reflection': reflect}
                                task_logs.append(log_entry)
                                
                                with st.expander(f"🧠 模型思考 (置信度: {score})", expanded=True):
                                    st.write(reflect)
                                    
                            elif node_name == 'optimize':
                                query = updates.get('search_query', '')
                                log_entry = {'type': 'optimize', 'query': query}
                                task_logs.append(log_entry)
                                st.write(f"🔄 优化搜索词: **{query}**")
                    
                    # 完成
                    status_container.update(label=f"✅ [{task.target_name}] 分析完成", state="complete", expanded=False)
                    
                    # 更新结果存储
                    score = final_state.get('confidence_score', 0.0)
                    results[task.task_id]['score'] = score
                    results[task.task_id]['report'] = final_state.get('report_content', '暂无内容')
                    results[task.task_id]['reflection'] = final_state.get('reflection', '')
                    # 这里依然保存，但按照用户要求，最终展示时不展示"未用到"的冗余新闻。
                    # report 本身通常包含引用。
                    results[task.task_id]['search_results'] = final_state.get('search_results', '')
                    
                    if score > 0.6:
                        results[task.task_id]['status'] = 'success'
                    else:
                        results[task.task_id]['status'] = 'fail_low_score'
                
                except Exception as e:
                    results[task.task_id]['status'] = 'error'
                    results[task.task_id]['report'] = f"错误: {e}"
                    status_container.update(label="❌ 分析出错", state="error")
                    st.error(f"Error during execution: {e}")
                
                # 双重检查：如果循环结束但状态仍为 running，说明异常终止
                if results[task.task_id]['status'] == 'running':
                     results[task.task_id]['status'] = 'error'
                     results[task.task_id]['report'] = "任务异常中断：未知原因导致流程提前结束（可能为网络超时或迭代限制）。"
                     status_container.update(label="⚠️ 分析中断", state="error")
        progress_bar.progress(1.0)
        st.rerun() # 刷新以显示最终状态

    # --- 状态看板 ---
    
    st.subheader("📊 状态看板")
    
    # 创建卡片网格
    cols = st.columns(3)
    
    for idx, task in enumerate(tasks):
        res = results[task.task_id]
        status = res['status']
        col = cols[idx % 3]
        
        # 颜色编码
        if status == 'success':
            border_color = "gainsboro" # Streamlit 不支持原生卡片的自定义边框颜色
            emoji = "🟢"
            bg_color = "#e6fffa" # 浅绿色提示 (需要自定义 css 实现真正的背景色)
        elif status == 'fail_low_score':
            emoji = "🔴"
        elif status == 'error':
            emoji = "⚠️"
        else: # pending/running
            emoji = "⏳"
        
        with col:
            with st.container(border=True):
                st.markdown(f"### {emoji} {task.target_name}")
                # 本地化
                cn_type = {"SECTOR": "板块共振", "CONCEPT": "概念带动", "STOCK": "个股行情"}.get(task.task_type, task.task_type)
                st.caption(f"类型: {cn_type} | 包含股票: {len(task.involved_stocks)} 只")
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
    
    cn_type = {"SECTOR": "板块共振", "CONCEPT": "概念带动", "STOCK": "个股行情"}.get(task.task_type, task.task_type)
    st.markdown(f"### {task.target_name} ({cn_type})")
    
    # --- 透明度展示区域 ---
    # 用户要求：报告生成后展示最终用到的新闻 (以链接列表形式)
    
    with st.expander("🌍 引用新闻 (Relevant News)", expanded=False):
         news_data = res.get('search_results', [])
         if isinstance(news_data, list) and news_data:
              for item in news_data:
                   icon = f"https://www.google.com/s2/favicons?domain={item.get('url', '')}"
                   st.markdown(f"![icon]({icon}) [{item.get('title', 'No Title')}]({item.get('url', '#')})")
         elif news_data and isinstance(news_data, str):
              st.markdown(news_data)
         else:
              st.caption("暂无相关新闻数据")
    
    with st.expander("🧠 AI 思考与反思 (Thought Process)", expanded=False):
        if res.get('reflection'):
             st.write(res['reflection'])
        else:
             st.caption("暂无反思内容")

    # 状态提示
    if res['status'] == 'fail_low_score':
        st.error(f"⚠️ 置信度低 ({res['score']})。请参考反思并手动补充报告。")
    elif res['status'] == 'success':
        st.success(f"✅ 置信度合格 ({res['score']})")
    
    # 编辑器
    new_report = st.text_area("报告内容 (Markdown)", value=res['report'], height=400)
    
    if st.button("保存修改"):
        res['report'] = new_report
        st.session_state['task_results'][task_id] = res
        st.success("已保存！")
        st.rerun()

def main():
    st.set_page_config(page_title="StockReasonAgent", layout="wide")
    
    # Auth 逻辑
    login_widget(authenticator)
    
    if st.session_state["authentication_status"] is False:
        st.error('用户名或密码错误')
        return
    elif st.session_state["authentication_status"] is None:
        st.warning('请输入用户名和密码')
        return
        
    # 已认证
    with st.sidebar:
        st.title("StockReasonAgent")
        st.write(f"用户: *{st.session_state['name']}*")
        logout_widget(authenticator)

    # 初始化
    init_session_state()
    
    step = st.session_state['step']
    
    # 进度步骤指示器
    st.markdown(
        """
        <style>
        .step-container {
            display: flex;
            justify_content: space-between;
            margin-bottom: 20px;
        }
        .step {
            flex: 1;
            text-align: center;
            padding: 10px;
            margin: 0 5px;
            border-radius: 5px;
            border: 1px solid #ddd;
            color: #555;
        }
        .active {
            background-color: #e6f3ff; /* 浅蓝色背景 */
            color: #0066cc; /*更加易读的深蓝色文字，白色可能在浅蓝上对比度不够，或者保持白色如果背景够深*/
            border: 1px solid #0066cc;
            font-weight: bold;
        }
         /* 强制覆盖 Streamlit 默认样式以获得更好的白色文字效果 (如果是深蓝背景) 
            但用户要求是浅蓝背景。浅蓝背景配白色文字通常对比度不足。
            这里我使用浅蓝背景 + 深蓝文字，或者调整为深蓝背景 + 白色文字。
            用户原话："浅蓝色背景，白色文字"。
            尝试满足用户：light blue background, white text.
            Streamlit light blue (primary) is usually #ff4b4b? No, that's red.
            Let's use a standard light blue.
         */
        .user-active {
            background-color: #4da6ff; /* 稍微深一点的浅蓝，以保证白色文字可见 */
            color: white !important;
            border: none;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True
    )
    
    # 使用列来模拟自定义 HTML 结构可能不够灵活，直接写 HTML 或者继续使用 columns
    # 为了精确控制样式，直接渲染 HTML 是最简单的，但为了保持 st 布局一致性，继续用 columns + markdown
    
    step_names = ["1. 输入", "2. 分类调整", "3. 任务预览", "4. 执行报告"]
    cols = st.columns(4)
    
    for i, name in enumerate(step_names):
        s_num = i + 1
        with cols[i]:
            if s_num == step:
                # Active
                st.markdown(f"""
                    <div class="step user-active">
                        {name}
                    </div>
                """, unsafe_allow_html=True)
            else:
                # Inactive
                st.markdown(f"""
                    <div class="step">
                        {name}
                    </div>
                """, unsafe_allow_html=True)
            
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
