import streamlit as st
from query_helper import get_players

def show_players():
    """Display all players in a table, hiding internal IDs for UI clarity."""
    df = get_players().drop(columns=['player_id'], errors='ignore')
    st.subheader("All Players")
    st.dataframe(df)
