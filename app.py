import streamlit as st
import subprocess
import sys

st.set_page_config(page_title="BIST Tarayıcı", page_icon="📈")

pg = st.navigation([
    st.Page("pages/yenisistem.py", title="BIST Tarayıcı", icon="📈"),
])
pg.run()
