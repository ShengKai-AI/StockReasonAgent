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
    return authenticator

def login_widget(authenticator):
    """Renders the login widget."""
    # Returns (name, authentication_status, username)
    # But streamlit-authenticator handles session_state['authentication_status'] internally
    authenticator.login()

def logout_widget(authenticator):
    """Renders the logout button in the sidebar."""
    authenticator.logout("登出", "sidebar")
