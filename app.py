import streamlit as st
import pandas as pd
import json
from datetime import datetime
import uuid
from openai import OpenAI

from stock import StockInfo
from search import NewsSearch
import database
import auth_manager

# --- 初始化配置 ---
st.set_page_config(page_title="Project Causality - 异动归因 Agent", page_icon="🕵️", layout="wide")

# API Keys
try:
    DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except FileNotFoundError:
    st.error("未找到 Secrets 配置！请在 .streamlit/secrets.toml (本地) 或 Streamlit Cloud Secrets 中配置 DEEPSEEK_API_KEY 和 TAVILY_API_KEY。")
    st.stop()
except KeyError as e:
    st.error(f"Secrets 配置缺失: {e}。请检查配置文件。")
    st.stop()

# --- 全局样式注入 ---
st.markdown("""
<style>
/* 设定主色调 */
:root {
    --primary-color: #2962FF;
    --hover-color: #0039CB;
}

/* 全局按钮样式优化 (包括普通按钮和表单提交按钮) */
div.stButton > button:first-child, 
div[data-testid="stFormSubmitButton"] > button:first-child {
    background-color: var(--primary-color);
    color: white;
    font-weight: 600;
    border-radius: 8px;
    border: none;
    padding: 0.5rem 1rem;
    transition: all 0.2s ease-in-out;
}

/* 按钮悬停效果 */
div.stButton > button:first-child:hover,
div[data-testid="stFormSubmitButton"] > button:first-child:hover {
    background-color: var(--hover-color);
    box-shadow: 0 4px 12px rgba(41, 98, 255, 0.3);
    transform: translateY(-1px);
    color: white;
}

/* 按钮点击效果 */
div.stButton > button:first-child:active,
div[data-testid="stFormSubmitButton"] > button:first-child:active {
    transform: translateY(1px);
}

/* --- 侧边栏历史记录按钮专用样式 --- */
section[data-testid="stSidebar"] div.stButton > button {
    background-color: transparent !important;
    color: #4A4A4A !important;
    border: 1px solid transparent !important;
    font-size: 0.9rem !important;      
    padding: 0.25rem 0.5rem !important; 
    margin: 0px !important;
    font-weight: 400 !important;
    text-align: left !important;
    justify-content: flex-start !important; 
}

section[data-testid="stSidebar"] div.stButton > button:hover {
    background-color: #E0E0E0 !important;
    color: #222 !important;
    box_shadow: none !important;
    transform: none !important;
}

/* 当前选中的会话 (Primary) */
section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
    background-color: #E3F2FD !important; 
    color: #1565C0 !important;           
    border: 1px solid #BBDEFB !important;
    font-weight: 600 !important;
}

section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
    background-color: #BBDEFB !important; 
    color: #0D47A1 !important;
}

/* 开启新对话按钮特殊样式 */
section[data-testid="stSidebar"] .block-container div[data-testid="stVerticalBlock"] > div:first-child button {
    background-color: transparent !important;
    color: #2962FF !important; 
    border: 1px dashed #2962FF !important;
    font-weight: 600 !important;
}

/* 移除列间距，模拟按钮合并 */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    gap: 0px !important;
    align-items: center; 
}

/* 左侧：会话名称按钮修正 */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(1) [data-testid="stButton"] button {
    border-top-right-radius: 0px !important;
    border-bottom-right-radius: 0px !important;
    border-right: none !important; 
    margin-right: 0px !important;
    height: auto !important;
    min-height: 2.8rem; 
}

/* 右侧：Popover 菜单按钮修正 */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(2) [data-testid="stPopover"] button {
    border-top-left-radius: 0px !important;
    border-bottom-left-radius: 0px !important;
    border-left: none !important; 
    margin-left: 0px !important;
    background-color: transparent !important; 
    border: 1px solid rgba(128, 128, 128, 0.2) !important; 
    border-left: none !important; 
    color: inherit !important;
    height: auto !important;
    min-height: 2.8rem;
}

[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-of-type(2) [data-testid="stPopover"] button:hover {
    background-color: rgba(128, 128, 128, 0.1) !important;
}
</style>
""", unsafe_allow_html=True)

# 初始化工具
if 'stock_tool' not in st.session_state:
    st.session_state.stock_tool = StockInfo()
if 'search_tool' not in st.session_state:
    st.session_state.search_tool = NewsSearch(TAVILY_API_KEY)
if 'llm_client' not in st.session_state:
    st.session_state.llm_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://ark.cn-beijing.volces.com/api/v3")

# ==========================================
# 核心业务逻辑封装
# ==========================================
def render_main_interface(username):
    """只有登录后才会渲染的主界面逻辑"""
    
    # --- 会话状态管理 Helpers (DB 版本) ---
    def load_session_into_state(session_data):
        st.session_state.step = session_data.get("step", 1)
        st.session_state.stock_code = session_data.get("stock_code", "")
        st.session_state.quant_data = session_data.get("quant_data", None)
        st.session_state.generated_query = session_data.get("generated_query", "")
        st.session_state.search_results = session_data.get("search_results", None)
        st.session_state.selected_news_indices = session_data.get("selected_news_indices", [])
        st.session_state.final_report = session_data.get("final_report", "")

    def get_current_session_data():
        return {
            "step": st.session_state.step,
            "stock_code": st.session_state.stock_code,
            "quant_data": st.session_state.quant_data,
            "generated_query": st.session_state.generated_query,
            "search_results": st.session_state.search_results,
            "selected_news_indices": st.session_state.selected_news_indices,
            "final_report": st.session_state.get("final_report", "")
        }

    def save_state_to_db(title=None):
        if 'current_session_id' in st.session_state:
            data = get_current_session_data()
            database.save_session(username, st.session_state.current_session_id, data, title)

    def start_new_session_action():
        new_id = str(uuid.uuid4())
        empty_data = {
            "step": 1,
            "stock_code": "SH600000",
            "quant_data": None,
            "generated_query": "",
            "search_results": None,
            "selected_news_indices": [],
            "final_report": ""
        }
        # 保存新会话到 DB
        database.save_session(username, new_id, empty_data, "新对话")
        # 切换状态
        st.session_state.current_session_id = new_id
        load_session_into_state(empty_data)
        st.rerun()

    def switch_session_action(session_id, session_data):
        save_state_to_db() # 切换前保存旧的
        st.session_state.current_session_id = session_id
        load_session_into_state(session_data)
        st.rerun()

    def go_to_step_action(step):
        st.session_state.step = step
        save_state_to_db()
        st.rerun()

    def reset_app_action():
        start_new_session_action()

    # --- 初始化当前会话 (首次加载) ---
    if 'current_session_id' not in st.session_state:
        # 尝试加载该用户最新的一个会话
        existing = database.get_user_sessions(username)
        if existing:
            latest = existing[0]
            st.session_state.current_session_id = latest['id']
            load_session_into_state(latest['session_data'])
        else:
            # 无历史，新建
            start_new_session_action()

    # 确保 step 等变量存在
    if 'step' not in st.session_state:
        existing = database.get_user_sessions(username)
        if existing and 'current_session_id' in st.session_state:
            # 找到对应 ID 的数据
            target = next((s for s in existing if s['id'] == st.session_state.current_session_id), None)
            if target:
                load_session_into_state(target['session_data'])
            else:
                 start_new_session_action()
        else:
            start_new_session_action()

    # --- Sidebar 渲染 ---
    with st.sidebar:
        if st.button("➕ 开启新对话", use_container_width=True):
            start_new_session_action()

        st.markdown("### 历史记录")
        
        # 从 DB 获取列表
        all_sessions = database.get_user_sessions(username)
        
        # 模态框逻辑
        @st.dialog("重命名对话")
        def show_rename_dialog(session_id, current_title):
            new_name = st.text_input("请输入新名称", value=current_title)
            if st.button("确认修改", type="primary"):
                database.rename_session(session_id, new_name)
                st.rerun()

        @st.dialog("确认删除")
        def show_delete_dialog(session_id, title):
            st.warning(f"确定要删除对话“{title}”吗？此操作无法撤销。")
            if st.button("确认删除", type="primary"):
                database.delete_session(session_id)
                if session_id == st.session_state.current_session_id:
                     if 'current_session_id' in st.session_state:
                         del st.session_state.current_session_id
                st.rerun()

        for s in all_sessions:
            col1, col2 = st.columns([0.85, 0.15])
            is_active = (s['id'] == st.session_state.get('current_session_id'))
            btn_type = "primary" if is_active else "secondary"
            
            with col1:
                 if st.button(s['title'], key=f"btn_{s['id']}", use_container_width=True, type=btn_type):
                     switch_session_action(s['id'], s['session_data'])
            
            with col2:
                 with st.popover(" ", use_container_width=True):
                     if st.button("重命名", key=f"ren_btn_{s['id']}", use_container_width=True):
                         show_rename_dialog(s['id'], s['title'])
                     if st.button("删除", key=f"del_btn_{s['id']}", use_container_width=True):
                         show_delete_dialog(s['id'], s['title'])

        st.markdown("---")
        st.markdown("Project Causality v0.1")

    # --- 主界面 UI ---
    st.title("智能异动归因 Agent")

    # Step 1
    if st.session_state.step == 1:
        st.subheader("Step 1: 目标锁定")
        code_input = st.text_input("请输入证券代码 (Ticker Symbol)", value=st.session_state.stock_code, placeholder="例如: SH600000 或 SZ000001")
        st.caption("支持上交所 (SH) 与深交所 (SZ) 主板/科创板/创业板标的")
        
        analyze_btn = st.button("开始分析", use_container_width=False)
        if analyze_btn:
            if not code_input:
                st.warning("⚠️ 请输入证券代码")
            elif not (code_input.upper().startswith("SH") or code_input.upper().startswith("SZ")):
                st.error("⛔️ 格式错误：必须包含市场标识前缀 (SH/SZ)，请修正后重试。")
            else:
                with st.spinner("正在连接行情数据中心..."):
                    stock_tool = st.session_state.stock_tool
                    stock_data = stock_tool.get_stock_realtime_data(code_input)
                
                if isinstance(stock_data, str):
                    st.error(stock_data)
                else:
                    market_analysis = stock_tool.get_market_context(code_input, stock_data)
                    st.session_state.quant_data = {**stock_data, **market_analysis}
                    st.session_state.stock_code = code_input
                    
                    # 自动生成 Query
                    stock_name = st.session_state.quant_data['股票名称']
                    strategy = st.session_state.quant_data['异动类型']
                    sector_name = st.session_state.quant_data['板块名称']
                    if strategy == "板块共振":
                        query = f"{sector_name} 行业利好 政策"
                    else:
                        query = f"{stock_name} 股价 原因 公告 业绩 传闻"
                    st.session_state.generated_query = query
                    
                    # 自动保存并跳转
                    save_state_to_db(title=f"{stock_name} {code_input}") 
                    go_to_step_action(2)

    # Step Dashboard
    if st.session_state.step >= 2:
        if st.session_state.quant_data:
            data = st.session_state.quant_data
            col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1.2])
            col1.metric("股票名称", f"{data['股票名称']} ({data['股票代码']})")
            col2.metric("最新价格", f"{data['当前价格']}元", data['今日涨跌幅'])
            col3.metric("所属行业", data['所属行业'], data['板块涨跌幅'])
            col4.metric("异动类型", data['异动类型'], f"偏离度 {data['相对强弱']}")
            st.info(f"💡 策略分析: {data['搜索策略建议']}")
            st.markdown("---")

        if st.session_state.step == 2:
            st.subheader("Step 2: 搜索关键词确认")
            st.write("Agent 已根据行情特征生成搜索关键词，您可以手动修改以获得更精准的结果：")
            user_query = st.text_input("搜索关键词", value=st.session_state.generated_query, label_visibility="collapsed")
            
            if st.button("确认并搜索"):
                st.session_state.generated_query = user_query
                with st.spinner(f"正在全网搜索 '{user_query}' ..."):
                    search_tool = st.session_state.search_tool
                    results = search_tool.search_attribution_news(query=user_query)
                    if isinstance(results, dict) and 'results' in results:
                         st.session_state.search_results = results['results']
                    else:
                         st.error(f"搜索出错: {results}")
                         st.stop()
                    st.session_state.selected_news_indices = list(range(len(st.session_state.search_results)))
                    go_to_step_action(3)
        else:
             st.info(f"✅ 确认搜索关键词: {st.session_state.generated_query}")

    # Step 3
    if st.session_state.step >= 3:
        st.subheader("Step 3: 情报筛选 (Human-in-the-loop)")
        if st.session_state.step == 3:
            st.write("请勾选您认为【有效】的新闻线索，剔除旧闻或噪音：")
            results = st.session_state.search_results
            if not results:
                st.warning("未搜索到相关新闻。")
                if st.button("跳过新闻，直接归因"):
                     st.session_state.selected_news_indices = []
                     go_to_step_action(4)
            else:
                with st.form("news_selection_form"):
                    selected_indices = []
                    for i, item in enumerate(results):
                        is_checked = st.checkbox(
                            f"[{item.get('published_date', '未知日期')}] {item.get('title')}",
                            value=True,
                            key=f"news_{i}"
                        )
                        st.caption(f"来源: {item.get('url')} | 摘要: {item.get('content')[:100]}...")
                        if is_checked:
                            selected_indices.append(i)
                    
                    submitted = st.form_submit_button("生成报告")
                    if submitted:
                        st.session_state.selected_news_indices = selected_indices
                        go_to_step_action(4)
        else:
            num_selected = len(st.session_state.selected_news_indices)
            st.success(f"已筛选出 {num_selected} 条有效情报")
            with st.expander("点击查看已选情报列表"):
                 for idx in st.session_state.selected_news_indices:
                     if idx < len(st.session_state.search_results):
                         item = st.session_state.search_results[idx]
                         st.markdown(f"- **{item.get('title')}** `[{item.get('published_date')}]`")

    # Step 4
    if st.session_state.step == 4:
        st.subheader("Step 4: 深度归因报告")
        
        report_container = st.empty()
        
        if st.session_state.get("final_report"):
            report_container.markdown(st.session_state.final_report)
            st.info("📌 以上为历史生成报告")
            if st.button("🔄 重新生成归因报告"):
                 st.session_state.final_report = "" 
                 st.rerun()
        else:
            # 数据准备
            quant_data = st.session_state.quant_data
            all_results = st.session_state.search_results
            selected_indices = st.session_state.selected_news_indices
            final_news_list = [all_results[i] for i in selected_indices]
            news_text = json.dumps(final_news_list, ensure_ascii=False, indent=2)
            used_query = st.session_state.generated_query
            current_date = datetime.now().strftime("%Y-%m-%d")
            quant_str = json.dumps(quant_data, ensure_ascii=False, indent=2)
            
            system_prompt = f"""
            你是一位专业的 A 股异动归因分析师。今天是 {current_date}。
            
            你的任务是结合【量化盘面数据】和【搜索到的新闻线索】，推理出股票涨跌的真实原因。
            
            ⚠️ 核心原则：
            1. **数据为王**：如果新闻说“大涨”，但量化数据显示只涨了 0.5%，请以量化数据为准。
            2. **筛选验证**：用户已经筛选过了新闻，请重点关注 Input 3 中的内容。
            3. **逻辑归因**：
               - 如果是【板块共振】，请重点总结行业层面的利好。
               - 如果是【独立行情】，请重点寻找个股层面的消息。
            4. **诚实原则**：如果新闻都是噪音，请直说“未发现驱动消息”。

            请输出 markdown 格式报告，包含：
            ## 📊 核心定性
            (一句话定性)
            ## 💡 主要驱动力
            (主要原因)
            ## 🕵️ 详细逻辑分析
            (结合数据和新闻)
            ## ⚠️ 风险提示
            """

            user_prompt = f"""
            【输入 1：量化盘面数据】
            {quant_str}

            【输入 2：使用的搜索词】
            {used_query}

            【输入 3：用户筛选后的有效新闻片段】
            {news_text}

            请开始分析：
            """
            
            full_response = ""
            with st.spinner("🧠 DeepSeek 大脑飞速运转中..."):
                try:
                    client = st.session_state.llm_client
                    response = client.chat.completions.create(
                        model="deepseek-v3-2-251201",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.1,
                        stream=True
                    )
                    
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            report_container.markdown(full_response + "▌")
                    
                    report_container.markdown(full_response)
                    st.session_state.final_report = full_response
                    save_state_to_db()
                    
                except Exception as e:
                    st.error(f"归因生成失败: {str(e)}")

    if st.button("开始新一轮分析"):
        reset_app_action()

# ==========================================
# 入口点 (Entry Point)
# ==========================================
if __name__ == "__main__":
    # 1. 初始化数据库
    database.init_db()
    
    # 2. 认证逻辑
    authenticator = auth_manager.init_auth()
    
    # 渲染登录界面
    # streamlit_authenticator 会自动处理 login form 的渲染和 session_state 的更新
    auth_manager.login_widget(authenticator)

    # 3. 检查登录状态
    if st.session_state["authentication_status"]:
        # 登录成功: 显示侧边栏用户信息和登出按钮
        with st.sidebar:
            st.write(f"欢迎, *{st.session_state['name']}*")
            auth_manager.logout_widget(authenticator)
            st.divider()
        
        # 4. 进入主界面
        # 传入 username，确保每个用户看到自己的历史记录
        render_main_interface(st.session_state["username"])
        
    elif st.session_state["authentication_status"] is False:
        st.error('用户名或密码错误')
    elif st.session_state["authentication_status"] is None:
        st.warning('请登录')
