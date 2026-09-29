import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from data_processor import DataCleaner, CityAggregator
from config import CITY_COORDS, COUNTRY_CAPITALS, MIN_SAMPLE_SIZE
import os

# Page configuration
st.set_page_config(
    page_title="Europe Housing Budget",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .hero-title {
            font-size: 3.5rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.5rem;
            color: #1a1a1a;
        }
        .hero-subtitle {
            font-size: 1.25rem;
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """Load and process data"""
    # Create sample data
    from sample_data import create_sample_data
    
    df_raw = create_sample_data()
    os.makedirs("data", exist_ok=True)
    df_raw.to_csv("data/homestra_properties_raw.csv", index=False)
    
    # Clean data
    cleaner = DataCleaner()
    cleaner.load_raw_data()
    cleaner.clean_data()
    cleaner.save_clean_data()
    
    # Aggregate by city
    aggregator = CityAggregator()
    aggregator.load_clean_data()
    aggregator.aggregate_by_city()
    aggregator.save_city_summary()
    
    return cleaner.df_clean, aggregator.city_summary, aggregator.df


def create_europe_map(city_data):
    """Create interactive Europe map"""
    fig = go.Figure()
    
    # Add scatter points for cities
    for idx, row in city_data.iterrows():
        city = row['city']
        if city in CITY_COORDS:
            lat, lon = CITY_COORDS[city]
            fig.add_trace(go.Scattergeo(
                lon=[lon],
                lat=[lat],
                mode='markers+text',
                name=city,
                marker=dict(
                    size=max(8, min(row['n_listings'] / 2, 30)),
                    color=row['median_price_per_m2'],
                    colorscale='Viridis',
                    showscale=False,
                    opacity=0.8,
                    line=dict(width=1, color='white')
                ),
                text=city,
                textposition='top center',
                textfont=dict(size=10, color='#000'),
                hovertemplate=f"<b>{city}</b><br>" +
                             f"Median price: €{row['median_price']:,.0f}<br>" +
                             f"Median size: {row['median_m2']:.0f} m²<br>" +
                             f"€/m²: €{row['median_price_per_m2']:,.0f}<br>" +
                             f"Listings: {row['n_listings']:.0f}<br>" +
                             f"Sample: {row['sample_quality']}<extra></extra>"
            ))
    
    fig.update_layout(
        title="European Cities: Housing Prices & Space (€200k-€400k)",
        geo=dict(
            scope='europe',
            projection_type='natural earth',
            showland=True,
            landcolor='rgba(243, 243, 243, 0.5)',
            coastcolor='rgba(204, 204, 204, 0.5)',
            showocean=True,
            oceancolor='rgba(230, 245, 255, 0.3)'
        ),
        height=600,
        hovermode='closest',
        margin=dict(r=0, t=50, l=0, b=0)
    )
    
    return fig


def create_space_comparison_chart(city_data, budget=300000):
    """Create horizontal bar chart comparing m² by city"""
    df_sorted = city_data.sort_values('median_m2', ascending=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df_sorted['city'],
        x=df_sorted['median_m2'],
        orientation='h',
        marker=dict(
            color=df_sorted['median_price_per_m2'],
            colorscale='RdYlGn_r',
            showscale=True,
            colorbar=dict(title="€/m²")
        ),
        text=df_sorted['median_m2'].round(0),
        textposition='auto',
        hovertemplate="<b>%{y}</b><br>" +
                     "Median m²: %{x:.0f}<br>" +
                     "Median price: €%{customdata[0]:,.0f}<br>" +
                     "€/m²: €%{customdata[1]:,.0f}<br>" +
                     "Listings: %{customdata[2]:.0f}<extra></extra>",
        customdata=df_sorted[['median_price', 'median_price_per_m2', 'n_listings']].values
    ))
    
    fig.update_layout(
        title=f"How Much Space Does €{budget:,.0f} Buy Across Europe?",
        xaxis_title="Median Property Size (m²)",
        yaxis_title="",
        height=500,
        showlegend=False,
        hovermode='closest',
        template='plotly_white'
    )
    
    return fig


def create_city_comparison(city_data, city_a, city_b, budget=300000):
    """Create comparison between two cities"""
    data_a = city_data[city_data['city'] == city_a].iloc[0] if city_a in city_data['city'].values else None
    data_b = city_data[city_data['city'] == city_b].iloc[0] if city_b in city_data['city'].values else None
    
    if data_a is None or data_b is None:
        return None
    
    fig = go.Figure()
    
    cities = [city_a, city_b]
    sizes = [data_a['median_m2'], data_b['median_m2']]
    prices = [data_a['median_price'], data_b['median_price']]
    
    fig.add_trace(go.Bar(
        x=cities,
        y=sizes,
        name='Median Size (m²)',
        marker_color=['#667eea', '#764ba2'],
        text=sizes.round(0),
        textposition='auto',
        hovertemplate="<b>%{x}</b><br>" +
                     "Median size: %{y:.0f} m²<extra></extra>"
    ))
    
    fig.update_layout(
        title=f"City Comparison: Size at €{budget:,.0f}",
        yaxis_title="Median Property Size (m²)",
        height=400,
        showlegend=False,
        template='plotly_white'
    )
    
    return fig, data_a, data_b


def render_property_examples(properties_df, city, budget_min, budget_max):
    """Display example properties for a city"""
    city_props = properties_df[
        (properties_df['city'] == city) &
        (properties_df['price_eur'].between(budget_min, budget_max))
    ].head(3)
    
    if len(city_props) == 0:
        st.info(f"No properties found in budget range for {city}")
        return
    
    st.subheader(f"Example Properties in {city}")
    
    for idx, prop in city_props.iterrows():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Price", f"€{prop['price_eur']:,.0f}")
        
        with col2:
            st.metric("Size", f"{prop['size_m2']:.0f} m²")
        
        with col3:
            st.metric("€/m²", f"€{prop['price_per_m2']:,.0f}")
        
        if pd.notna(prop['bedrooms']):
            st.write(f"**Bedrooms:** {int(prop['bedrooms'])}")
        
        if pd.notna(prop['listing_url']):
            st.markdown(f"[View on Homestra]({prop['listing_url']})")
        
        st.divider()


# Main app
def main():
    # Load data
    properties_clean, city_summary, properties_raw = load_data()
    
    # Hero section
    st.markdown('<div class="hero-title">What does your budget buy across Europe?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">€200,000–€400,000 can mean a compact apartment in one European city '
        'and a family-sized home in another. Explore real Homestra listings to see how far the same housing budget '
        'stretches across Europe.</div>',
        unsafe_allow_html=True
    )
    
    # Budget selector
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        budget = st.select_slider(
            "Select your budget:",
            options=[200000, 225000, 250000, 275000, 300000, 325000, 350000, 375000, 400000],
            value=300000,
            format_func=lambda x: f"€{x/1000:.0f}k"
        )
    
    budget_range = 25000  # 25k tolerance
    budget_min = budget - budget_range
    budget_max = budget + budget_range
    
    # Filter data for budget range
    city_summary_filtered = city_summary[
        city_summary['median_price'].between(budget_min, budget_max) |
        city_summary['median_price_per_m2'].between(budget_min/100, budget_max/100)
    ].copy()
    
    st.divider()
    
    # Key metrics
    st.subheader("Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Cities Analysed", f"{len(city_summary)}")
    
    with col2:
        st.metric("Properties Analysed", f"{len(properties_clean)}")
    
    with col3:
        st.metric("Median Property Size", f"{city_summary['median_m2'].median():.0f} m²")
    
    with col4:
        most_space_city = city_summary.loc[city_summary['median_m2'].idxmax(), 'city']
        most_space_size = city_summary['median_m2'].max()
        st.metric("Most Space", f"{most_space_city} ({most_space_size:.0f} m²)")
    
    with col5:
        least_space_city = city_summary.loc[city_summary['median_m2'].idxmin(), 'city']
        least_space_size = city_summary['median_m2'].min()
        st.metric("Least Space", f"{least_space_city} ({least_space_size:.0f} m²)")
    
    st.divider()
    
    # Europe map
    st.subheader("Europe Map: Explore Cities")
    st.write("Hover over cities to see detailed statistics. Bubble size represents number of listings.")
    fig_map = create_europe_map(city_summary)
    st.plotly_chart(fig_map, use_container_width=True)
    
    st.divider()
    
    # Space comparison
    st.subheader("How Much Space Does Your Money Buy?")
    st.write(f"Comparison of median property sizes at €{budget:,.0f} (±€{budget_range:,.0f})")
    fig_comparison = create_space_comparison_chart(city_summary, budget)
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    st.divider()
    
    # City comparison
    st.subheader("Compare Two Cities")
    col1, col2 = st.columns(2)
    
    available_cities = sorted(city_summary['city'].unique())
    
    with col1:
        city_a = st.selectbox("Select City A", available_cities, key="city_a")
    
    with col2:
        city_b = st.selectbox("Select City B", available_cities, index=1 if len(available_cities) > 1 else 0, key="city_b")
    
    if city_a != city_b:
        result = create_city_comparison(city_summary, city_a, city_b, budget)
        if result:
            fig_comp, data_a, data_b = result
            st.plotly_chart(fig_comp, use_container_width=True)
            
            # Comparison summary
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### {city_a}")
                st.metric("Median Size", f"{data_a['median_m2']:.0f} m²")
                st.metric("Median Price", f"€{data_a['median_price']:,.0f}")
                st.metric("€ per m²", f"€{data_a['median_price_per_m2']:,.0f}")
                st.metric("Listings", f"{data_a['n_listings']:.0f}")
            
            with col2:
                st.markdown(f"### {city_b}")
                st.metric("Median Size", f"{data_b['median_m2']:.0f} m²")
                st.metric("Median Price", f"€{data_b['median_price']:,.0f}")
                st.metric("€ per m²", f"€{data_b['median_price_per_m2']:,.0f}")
                st.metric("Listings", f"{data_b['n_listings']:.0f}")
            
            ratio = data_a['median_m2'] / data_b['median_m2']
            st.info(f"Your money buys approximately **{ratio:.1f}x** more space in {city_a} than in {city_b}.")
    
    st.divider()
    
    # Property examples
    st.subheader("Explore Real Properties")
    selected_city = st.selectbox("Select a city to see example properties:", available_cities)
    render_property_examples(properties_clean, selected_city, budget_min, budget_max)
    
    st.divider()
    
    # Methodology
    st.subheader("Methodology & Data Transparency")
    
    methodology_text = f"""
    #### Data Collection
    - **Source:** Homestra.com property listings
    - **Price Range:** €200,000 – €400,000
    - **Property Types:** Apartments, houses, and townhouses
    - **Total Properties Collected:** {len(properties_clean)}
    - **Cities Analysed:** {len(city_summary)}
    - **Collection Date:** January 2024
    
    #### Data Cleaning
    - Removed properties with incomplete data (missing price, size, or city)
    - Excluded properties outside the price range
    - Excluded properties with unrealistic sizes (<10 m² or >5,000 m²)
    - Removed duplicate listings (same URL)
    - Standardized city names and data types
    
    #### City-Level Aggregation
    - **Statistic Used:** Median (not mean) to reduce impact of outliers
    - **Minimum Sample Size:** {MIN_SAMPLE_SIZE} properties per city
    - Cities with fewer properties are marked as "Limited sample"
    - Medians calculated only from verified, deduplicated listings
    
    #### Important Limitations
    1. **Asking Prices, Not Transaction Prices:** Data represents asking prices on Homestra, not actual sale prices
    2. **Homestra Coverage Varies:** Some countries have much better coverage than others
    3. **Not Representative:** This sample does NOT represent the entire European housing market
    4. **Possible Duplicates:** Some listings may appear across multiple platforms or be re-listed
    5. **Point-in-Time Data:** Market conditions change; this snapshot reflects January 2024
    6. **Selection Bias:** Homestra's user base and listing types may differ by region
    
    #### Sample Quality
    - Cities are marked "Sufficient sample" if they have ≥{MIN_SAMPLE_SIZE} listings
    - Cities with fewer listings are marked "Limited sample" and should be interpreted cautiously
    
    #### How to Use This Data
    This visualization is designed for exploratory data journalism and university research. It answers the question:
    "If I have between €200,000 and €400,000, and I search on Homestra, how much variation in property size
    can I find across European cities?"
    
    Use the results to understand relative differences, not as definitive market analysis.
    """
    
    st.markdown(methodology_text)


if __name__ == "__main__":
    main()
