import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import streamlit as st

CONFIG_FILE = "config.yaml"

def init_auth():
    """Configures and returns the Main Authenticator object."""
    with open(CONFIG_FILE) as file:
        config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        # The preauthorized section is optional but good practice
        # config['preauthorized'] 
    )
    
    # [DEMO] 强制自动登录演示账号
    if 'authentication_status' not in st.session_state or st.session_state['authentication_status'] is None:
        st.session_state["authentication_status"] = True
        st.session_state["name"] = "演示管理员"
        st.session_state["username"] = "admin"
        
    return authenticator

def login_widget(authenticator):
    """Renders the login widget."""
    # Returns (name, authentication_status, username)
    # But streamlit-authenticator handles session_state['authentication_status'] internally
    
    # [DEMO] 如果已经强制登录，不要渲染登录组件，否则可能会重置状态或显示不需要的内容
    if st.session_state.get('authentication_status'):
        return
        
    authenticator.login()

def logout_widget(authenticator):
    """Renders the logout button in the sidebar."""
    authenticator.logout("登出", "sidebar")
