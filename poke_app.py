import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Set page config
st.set_page_config(
    page_title="Card Trading Dashboard",
    page_icon="🃏",
    layout="wide"
)

# Assuming jwt token is stored in environment variable or config
jwt="eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJjYXJkdHJhZGVyLXByb2R1Y3Rpb24iLCJzdWIiOiJhcHA6MTI3ODEiLCJhdWQiOiJhcHA6MTI3ODEiLCJleHAiOjQ4ODc1Mzc4MTgsImp0aSI6IjIzNmVkYzRkLTJiZGMtNGYzMi05ZTgwLTU3OWQ2MGU5ZGM5YyIsImlhdCI6MTczMTg2NDIxOCwibmFtZSI6Ikd1c3RhcjggQXBwIDIwMjQxMTE3MTgyMzM4In0.uC93jLBpZjR7mPszmdbNSiQwZV5JrR-BRCDwp9FWfpXP9ip_zex8eyEGAIoZ7JHBpkuZPGZ2ezOVJPdYUCL1-JRr7S3pgkU-C4NMMPcJu3QRJ1mMbT0XcWBodnnnaY26uxFkRlXY-cKxmKV5ATR1KDs9hLWNE7mMKFx_-pNKwHvLp5P02WFWvLwkd76ZBRBubIJyFak0eRBn-344eb-2dD-t5gHJxDc7-vbnxlSqe1tTveqOThSEhzwJlVQDCQiUqOjy3ZnWeMLm3x1Wc36XhQbE-WpCZwGAbkPSXFp5UdcUTdJ9-ggktsHrwSCfGxjylPiGtPU5iLeTLzKhWf7wkw"

base_url = "https://api.cardtrader.com/api/v2"

# Cache the API calls to improve performance
@st.cache(ttl=3600)
def get_games():
    """Fetch available games from the API"""
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(f"{base_url}/games", headers=headers)
    return pd.DataFrame(response.json()['array'])

@st.cache(ttl=3600)
def get_expansions():
    """Fetch all expansions from the API"""
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(f"{base_url}/expansions", headers=headers)
    return pd.DataFrame(response.json())

@st.cache(ttl=3600)
def get_cards(expansion_id, language="it"):
    """Fetch cards for a specific expansion"""
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(
        f"{base_url}/marketplace/products",
        params={"expansion_id": expansion_id, "language": language},
        headers=headers
    )
    
    total = []
    for payload in response.json().values():
        expanded_data = []
        for item in payload:
            expanded_row = {}
            for key, value in item.items():
                if isinstance(value, str):
                    expanded_row[key] = value
                elif isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        new_key = nested_key
                        counter = 1
                        while new_key in expanded_row:
                            new_key = f"{nested_key}_{counter}"
                            counter += 1
                        expanded_row[new_key] = nested_value
            expanded_data.append(expanded_row)
            
        df = pd.DataFrame(expanded_data)
        try:
            filtered_df = (df
                .query("can_sell_via_hub == True")
                .query("pokemon_language == @language")
                .query("condition == 'Near Mint'")
                .sort_values(by="cents")
            )
            if not filtered_df.empty:
                card_data = {
                    "name": filtered_df.name_en.iloc[0],
                    "price": filtered_df.cents.iloc[0] / 100,  # Convert cents to currency
                    "id": filtered_df.id_1.iloc[0]
                }
                total.append(card_data)
        except:
            continue
            
    return pd.DataFrame(total)

# Main app layout
st.title("Card Trading Analysis Dashboard")

# Sidebar for filters
st.sidebar.header("Filters")

# Load games and expansions
games_df = get_games()
expansions_df = get_expansions()

# Set default game (Pokémon)
default_game = "Pokémon"
game_index = games_df[games_df['name'] == default_game].index.tolist()
default_game_idx = 0 if not game_index else int(game_index[0])

# Game selection
selected_game = st.sidebar.selectbox(
    "Select Game",
    options=games_df['display_name'].tolist(),
    index=default_game_idx
)

# Get game ID
game_id = games_df[games_df['display_name'] == selected_game]['id'].iloc[0]

# Filter expansions for selected game
game_expansions = expansions_df[expansions_df['game_id'] == game_id]

# Set default expansion (Base Set)
default_expansion = "Base Set"
expansion_list = game_expansions['name'].tolist()
try:
    default_exp_idx = expansion_list.index(default_expansion)
except ValueError:
    default_exp_idx = 0

selected_expansion = st.sidebar.selectbox(
    "Select Expansion",
    options=expansion_list,
    index=default_exp_idx
)

# Get expansion ID
expansion_id = game_expansions[game_expansions['name'] == selected_expansion]['id'].iloc[0]

# Language selection
languages = ['en', 'it', 'fr', 'de', 'es', "jp"]
default_lang_idx = languages.index('it')  # Set Italian as default

selected_language = st.sidebar.selectbox(
    "Select Language",
    options=languages,
    index=default_lang_idx
)

# Load card data
with st.spinner('Fetching card data...'):
    cards_df = get_cards(expansion_id, selected_language)

# Display metrics
col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Total Set Cost",
        f"€{cards_df['price'].sum():,.2f}",
        f"{len(cards_df)} cards"
    )

with col2:
    st.metric(
        "Average Card Price",
        f"€{cards_df['price'].mean():,.2f}",
        f"Median: €{cards_df['price'].median():,.2f}"
    )


# [Previous code remains the same until the visualization part]

# Create bar chart of top 10 most expensive cards with error bars
top_10_cards = cards_df.nlargest(10, 'price')

# Calculate standard deviation
std_dev = cards_df['price'].std()
error_bars = [std_dev] * len(top_10_cards)

# Create color scale based on prices
colors = px.colors.sequential.Viridis
normalized_prices = (top_10_cards['price'] - top_10_cards['price'].min()) / (top_10_cards['price'].max() - top_10_cards['price'].min())
bar_colors = [colors[int(np * (len(colors)-1))] for np in normalized_prices]

fig = go.Figure(data=[
    go.Bar(
        name='Price',
        x=top_10_cards['name'],
        y=top_10_cards['price'],
        error_y=dict(
            type='data',
            array=error_bars,
            visible=True,
            color='darkgray',
            thickness=1.5,
            width=3
        ),
        marker=dict(
            color=bar_colors
        ),
        hovertemplate="<b>%{x}</b><br>" +
                      "Price: €%{y:.2f}<br>" +
                      f"Std Dev: €{std_dev:.2f}<br>" +
                      "<extra></extra>"
    )
])

fig.update_layout(
    title='Top 10 Most Expensive Cards',
    xaxis_title='Card Name',
    yaxis_title='Price (€)',
    xaxis_tickangle=-45,
    height=500,
    showlegend=False,
    yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='LightGray'),
    xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='LightGray')
)

st.plotly_chart(fig)

# Add slider for top N expensive cards
st.header("Top N Most Expensive Cards")
n_cards = st.slider(
    "Select number of cards to display",
    min_value=1,
    max_value=min(50, len(cards_df)),  # Don't allow more than 50 or the total number of cards
    value=10  # Default value
)

# Display top N cards table with additional statistics
top_n_cards = cards_df.nlargest(n_cards, 'price').copy()
top_n_cards['Price'] = top_n_cards['price'].apply(lambda x: f"€{x:,.2f}")
top_n_cards['Relative to Average'] = (top_n_cards['price'] / top_n_cards['price'].mean()).apply(lambda x: f"{x:.2f}x")

# Create a nicely formatted table
display_df = top_n_cards[['name', 'Price', 'Relative to Average']].copy()
display_df.columns = ['Card Name', 'Price', 'Relative to Average']

# Simple dataframe display
st.dataframe(display_df)

# Show summary statistics
st.caption(f"""
    Statistics for top {n_cards} cards:
    - Total Value: €{top_n_cards['price'].sum():,.2f}
    - Average Price: €{top_n_cards['price'].mean():,.2f}
    - Price Range: €{top_n_cards['price'].min():,.2f} - €{top_n_cards['price'].max():,.2f}
""")