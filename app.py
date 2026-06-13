import streamlit as st
from queries.teams_query import show_teams
from queries.players_query import show_players
from queries.umpires_query import show_umpires
from queries.venues_query import show_venues

st.set_page_config(page_title="IPL Query Resolver", layout="centered")
st.title("IPL Query Resolver")

query = st.selectbox(
    "Select a query",
    ("All Teams", "All Players", "All Umpires", "All Venues"),
)

if query == "All Teams":
    show_teams()
elif query == "All Players":
    show_players()
elif query == "All Umpires":
    show_umpires()
else:
    show_venues()
