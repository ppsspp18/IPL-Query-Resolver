import streamlit as st
from query_helper import get_umpires

def show_umpires():
    """Display all umpires in a table, hiding internal IDs for UI clarity."""
    df = get_umpires().drop(columns=['umpire_id'], errors='ignore')
    st.subheader("All Umpires")
    st.dataframe(df)
