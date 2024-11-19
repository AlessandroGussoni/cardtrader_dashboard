import streamlit as st
import pandas as pd
import requests
import plotly.colors as cl
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
import os

ENV = "prod"

if ENV == "dev":

    with open("keys.json", "rb") as file:
        keys = json.load(file)

    jwt = keys["jwt"]

elif ENV == "prod":

    jwt = os.environ.get("jwt", "pass")

st.set_page_config(
    page_title="Card Trading Dashboard",
    page_icon="🃏",
    layout="wide"
)

base_url = "https://api.cardtrader.com/api/v2"

@st.cache(ttl=3600)
def get_games():
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(f"{base_url}/games", headers=headers)
    return pd.DataFrame(response.json()['array'])

@st.cache(ttl=3600)
def get_expansions():
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(f"{base_url}/expansions", headers=headers)
    return pd.DataFrame(response.json())


@st.cache(ttl=3600)
def get_cards(expansion_id, language, min_condition, hub_only):
    headers = {"Authorization": f"Bearer {jwt}"}
    response = requests.get(
        f"{base_url}/marketplace/products",
        params={"expansion_id": expansion_id, "language": language},
        headers=headers
    )
    
    condition_order = {
        'Near Mint': 0,
        'Slightly Played': 1,
        'Moderately Played': 2,
        'Played': 3,
        'Poor': 4
    }
    
    min_condition_value = condition_order[min_condition]
    acceptable_conditions = [cond for cond, value in condition_order.items() 
                           if value <= min_condition_value]
    
    condition_counts = {}
    total = []
    hub_cards_count = 0
    
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
            filtered_df = df[
                (df.pokemon_language == language) &
                (df.condition.isin(acceptable_conditions))
            ].sort_values(by=["condition", "cents"])
            
            if not filtered_df.empty:
                # Count conditions
                card_conditions = filtered_df.condition.value_counts()
                for cond, count in card_conditions.items():
                    condition_counts[cond] = condition_counts.get(cond, 0) + 1
                
                # Get best condition available for each card
                best_condition_df = filtered_df.sort_values(
                    by="condition",
                    key=lambda x: x.map(condition_order)
                ).groupby('name_en').first().reset_index()
                
                # Check if any seller offers the card via hub
                all_sellers_df = filtered_df[filtered_df.name_en == best_condition_df.name_en.iloc[0]]
                has_hub_seller = all_sellers_df.can_sell_via_hub.any()
                
                # Skip if hub_only is True and card has no hub sellers
                if hub_only and not has_hub_seller:
                    continue
                    
                if has_hub_seller:
                    hub_cards_count += 1
                
                final_price = None
                if hub_only:
                    # Only consider hub sellers
                    if not all_sellers_df[all_sellers_df.can_sell_via_hub == True].empty:
                        final_price = all_sellers_df[all_sellers_df.can_sell_via_hub == True].cents.min() / 100
                else:
                    # Consider all sellers
                    if not all_sellers_df[all_sellers_df.can_sell_via_hub == False].empty:
                        final_price = all_sellers_df[all_sellers_df.can_sell_via_hub == False].cents.min() / 100
                    elif not all_sellers_df[all_sellers_df.can_sell_via_hub == True].empty:
                        final_price = all_sellers_df[all_sellers_df.can_sell_via_hub == True].cents.min() / 100
                
                if final_price is not None:
                    card_data = {
                        "name": best_condition_df.name_en.iloc[0],
                        "price": final_price,
                        "id": best_condition_df.id_1.iloc[0],
                        "can_sell_via_hub": has_hub_seller,
                        "condition": best_condition_df.condition.iloc[0],
                        "price_std": filtered_df.cents.std() / 100
                    }
                    total.append(card_data)
        except:
            continue
            
    return pd.DataFrame(total), hub_cards_count, condition_counts


# Main app layout
st.title("Card Trading Analysis Dashboard")

# Sidebar filters
st.sidebar.header("Filters")

# Load games and expansions
games_df = get_games()
expansions_df = get_expansions()

# Game selection
default_game = "Pokémon"
game_index = games_df[games_df['name'] == default_game].index.tolist()
default_game_idx = 0 if not game_index else int(game_index[0])

selected_game = st.sidebar.selectbox(
    "Select Game",
    options=games_df['display_name'].tolist(),
    index=default_game_idx
)
hub_only = st.sidebar.checkbox('Only Show Hub Sellers', value=False)
game_id = games_df[games_df['display_name'] == selected_game]['id'].iloc[0]

# Filter expansions
game_expansions = expansions_df[expansions_df['game_id'] == game_id]

# Expansion selection
default_expansion = "Base Set"
expansion_list = game_expansions['name'].tolist()
default_exp_idx = expansion_list.index(default_expansion) if default_expansion in expansion_list else 0

selected_expansion = st.sidebar.selectbox(
    "Select Expansion",
    options=expansion_list,
    index=default_exp_idx
)

expansion_id = game_expansions[game_expansions['name'] == selected_expansion]['id'].iloc[0]

# Language selection
languages = ['en', 'it', 'fr', 'de', 'es', 'jp']
selected_language = st.sidebar.selectbox(
    "Select Language",
    options=languages,
    index=languages.index('it')
)

# Condition selection
conditions = ['Near Mint', 'Slightly Played', 'Moderately Played', 'Played', 'Poor']
selected_min_condition = st.sidebar.selectbox(
    "Select Minimum Condition",
    options=conditions,
    index=0
)

# Load card data
with st.spinner('Fetching card data...'):
    cards_df, hub_cards_count, condition_counts = get_cards(
        expansion_id, 
        selected_language, 
        selected_min_condition,
        hub_only
    )
# Display metrics
col1, col2, col3 = st.columns(3)

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

with col3:
    st.metric(
        "Hub-only Cards",
        f"{hub_cards_count}",
        f"{(hub_cards_count/len(cards_df)*100):.1f}% of total"
    )

# Add condition breakdown
st.subheader("Cards by Condition")
for condition in conditions:
    if condition in condition_counts:
        st.text(f"{condition}: {condition_counts[condition]} cards")

# Top 10 cards visualization
top_10_cards = cards_df.nlargest(10, 'price')
colors = cl.sequential.Viridis
fig = go.Figure(data=[
    go.Bar(
        name='Price',
        x=top_10_cards['name'],
        y=top_10_cards['price'],
        error_y=dict(
            type='data',
            array=top_10_cards['price_std'] / 1000,
            visible=True,
            color='darkgray',
            thickness=1.5,
            width=3
        ),
        marker=dict(
            color=[colors[int(np * (len(colors)-1))] for np in (
                (top_10_cards['price'] - top_10_cards['price'].min()) / 
                (top_10_cards['price'].max() - top_10_cards['price'].min())
            )]
        ),
        hovertemplate="<b>%{x}</b><br>" +
                      "Price: €%{y:.2f}<br>" +
                      "Std Dev: €%{error_y.array:.2f}<br>" +
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

# Top N cards section
st.header("Top N Most Expensive Cards")
n_cards = st.slider(
    "Select number of cards to display",
    min_value=1,
    max_value=min(50, len(cards_df)),
    value=10
)

top_n_cards = cards_df.nlargest(n_cards, 'price').copy()
top_n_cards['Price'] = top_n_cards['price'].apply(lambda x: f"€{x:,.2f}")
top_n_cards['Std Dev'] = top_n_cards['price_std'].apply(lambda x: f"€{x:,.2f}")
top_n_cards['Relative to Average'] = (top_n_cards['price'] / top_n_cards['price'].mean()).apply(lambda x: f"{x:.2f}x")
top_n_cards['Hub Only'] = top_n_cards['can_sell_via_hub'].apply(lambda x: 'Yes' if x else 'No')

display_df = top_n_cards[['name', 'Price', 'condition', 'Std Dev', 'Relative to Average', 'Hub Only']].copy()
display_df.columns = ['Card Name', 'Price', 'Condition', 'Std Dev', 'Relative to Average', 'Hub Only']

st.dataframe(display_df)

st.caption(f"""
    Statistics for top {n_cards} cards:
    - Total Value: €{top_n_cards['price'].astype(float).sum():,.2f}
    - Average Price: €{top_n_cards['price'].astype(float).mean():,.2f}
    - Price Range: €{top_n_cards['price'].astype(float).min():,.2f} - €{top_n_cards['price'].astype(float).max():,.2f}
    - Hub-only Cards: {top_n_cards['can_sell_via_hub'].sum()} ({(top_n_cards['can_sell_via_hub'].sum()/len(top_n_cards)*100):.1f}%)
""")
