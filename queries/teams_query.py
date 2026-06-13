import streamlit as st
from query_helper import get_teams

def show_teams():
    """Display all teams in a table, hiding internal IDs for UI clarity."""
    df = get_teams().drop(columns=['team_id'], errors='ignore')
    st.subheader("All Teams")
    st.dataframe(df)
