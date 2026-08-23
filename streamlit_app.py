import streamlit as st
import sys
import os

# Ensure the root folder is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Define the multi-page structure manually so Streamlit Cloud can find them 
# even though they are inside the dashboard/ folder
pages = {
    "Main": [
        st.Page("dashboard/app.py", title="Dashboard Home", icon="🏠", default=True),
    ],
    "Analysis": [
        st.Page("dashboard/pages/1_predictions.py", title="Predictions", icon="🎯"),
        st.Page("dashboard/pages/2_news_signals.py", title="News Signals", icon="📰"),
        st.Page("dashboard/pages/3_backtesting.py", title="Backtesting & Time Machine", icon="⏱️"),
    ]
}

pg = st.navigation(pages)
pg.run()
