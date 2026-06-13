import streamlit as st
from query_helper import get_venues

def show_venues():
    """Display all venues in a table, hiding internal IDs for UI clarity."""
    df = get_venues().drop(columns=['venue_id'], errors='ignore')
    st.subheader("All Venues")
    st.dataframe(df)
