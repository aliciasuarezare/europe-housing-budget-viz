import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_processor import DataCleaner, CityAggregator
from config import CITY_COORDS, COUNTRY_CAPITALS, MIN_SAMPLE_SIZE
import os

st.set_page_config(
    page_title="Europe Housing Budget Visualization",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }
        .hero-title { font-size: 3rem; font-weight: 700; text-align: center; margin-bottom: 0.5rem; color: #1a1a1a; }
        .hero-subtitle { font-size: 1.1rem; text-align: center; color: #666; margin-bottom: 2rem; line-height: 1.6; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    cleaner = DataCleaner()
    cleaner.load_raw_data()
    cleaner.clean_data()
    cleaner.save_clean_data()
    
    aggregator = CityAggregator()
    aggregator.load_clean_data()
    aggregator.aggregate_by_city()
    aggregator.save_city_summary()
    
    return cleaner.df_clean, aggregator.city_summary, aggregator.df

def create_europe_map(city_data):
    fig = go.Figure()
    for idx, row in city_data.iterrows():
        city = row['city']
        if city in CITY_COORDS:
            lat, lon = CITY_COORDS[city]
            fig.add_trace(go.Scattergeo(
                lon=[lon], lat=[lat], mode='markers+text', name=city,
                marker=dict(
                    size=max(8, min(row['n_listings'] / 2, 30)),
                    color=row['median_price_per_m2'],
                    colorscale='Viridis', opacity=0.8, line=dict(width=1, color='white')
                ),
                text=city, textposition='top center',
                hovertemplate=f"<b>{city}</b><br>Median: €{row['median_price']:,.0f}<br>{row['median_m2']:.0f} m² · €{row['median_price_per_m2']:,.0f}/m²<br>n={row['n_listings']:.0f}<extra></extra>"
            ))
    fig.update_layout(
        title="European Cities: Space vs Price (€200k–€400k)",
        geo=dict(scope='europe', projection_type='natural earth', showland=True, landcolor='rgba(243, 243, 243, 0.5)'),
        height=600, hovermode='closest', margin=dict(r=0, t=50, l=0, b=0)
    )
    return fig

def create_space_chart(city_data):
    df = city_data.sort_values('median_m2', ascending=True)
    fig = go.Figure(data=go.Bar(
        y=df['city'], x=df['median_m2'], orientation='h',
        marker=dict(color=df['median_price_per_m2'], colorscale='RdYlGn_r', showscale=True, colorbar=dict(title="€/m²")),
        text=df['median_m2'].round(0), textposition='auto',
        hovertemplate="<b>%{y}</b><br>%{x:.0f} m²<br>€%{customdata[0]:,.0f}<br>€%{customdata[1]:,.0f}/m²<br>n=%{customdata[2]:.0f}<extra></extra>",
        customdata=df[['median_price', 'median_price_per_m2', 'n_listings']].values
    ))
    fig.update_layout(
        title="How Much Space Does Your Budget Buy?",
        xaxis_title="Median m²", yaxis_title="", height=500,
        showlegend=False, template='plotly_white'
    )
    return fig

def compare_cities(city_data, city_a, city_b):
    if city_a not in city_data['city'].values or city_b not in city_data['city'].values:
        return None, None, None
    data_a = city_data[city_data['city'] == city_a].iloc[0]
    data_b = city_data[city_data['city'] == city_b].iloc[0]
    fig = go.Figure(data=go.Bar(
        x=[city_a, city_b], y=[data_a['median_m2'], data_b['median_m2']],
        marker_color=['#667eea', '#764ba2'],
        text=[f"{data_a['median_m2']:.0f}", f"{data_b['median_m2']:.0f}"],
        textposition='auto'
    ))
    fig.update_layout(title="Size Comparison", yaxis_title="m²", height=400, showlegend=False, template='plotly_white')
    return fig, data_a, data_b

def main():
    st.markdown('<div class="hero-title">What does your budget buy across Europe?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">€200k–€400k buys vastly different space depending on location. '
        'Explore real Homestra listings to understand the variation.</div>',
        unsafe_allow_html=True
    )
    
    # Load data
    try:
        properties_clean, city_summary, _ = load_data()
        
        if properties_clean.empty or city_summary.empty:
            st.warning(
                "⚠️ **No Homestra data available yet.**\n\n"
                "To populate this dashboard:\n\n"
                "1. Run: `python scraper.py` to collect real listings from Homestra.com\n"
                "2. This will download properties between €200k–€400k from European cities\n"
                "3. Run this dashboard again\n\n"
                "**Why not pre-loaded?** To ensure complete transparency: this project uses only "
                "real, verifiable Homestra listings. No mock or invented data is ever displayed."
            )
            return
        
        # Budget selector
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            budget = st.select_slider(
                "Select budget:",
                options=[200000, 225000, 250000, 275000, 300000, 325000, 350000, 375000, 400000],
                value=300000,
                format_func=lambda x: f"€{x/1000:.0f}k"
            )
        
        st.divider()
        
        # Metrics
        st.subheader("Overview")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Cities", f"{len(city_summary)}")
        with col2:
            st.metric("Properties", f"{len(properties_clean)}")
        with col3:
            st.metric("Median m²", f"{city_summary['median_m2'].median():.0f}")
        with col4:
            best = city_summary.loc[city_summary['median_m2'].idxmax()]
            st.metric("Most", f"{best['city']} ({best['median_m2']:.0f} m²)")
        with col5:
            worst = city_summary.loc[city_summary['median_m2'].idxmin()]
            st.metric("Least", f"{worst['city']} ({worst['median_m2']:.0f} m²)")
        
        st.divider()
        
        # Map
        st.subheader("European Cities Map")
        st.plotly_chart(create_europe_map(city_summary), use_container_width=True)
        
        st.divider()
        
        # Space comparison
        st.subheader("Ranked by Space")
        st.plotly_chart(create_space_chart(city_summary), use_container_width=True)
        
        st.divider()
        
        # City comparison
        st.subheader("Compare Two Cities")
        col1, col2 = st.columns(2)
        cities_list = sorted(city_summary['city'].unique())
        with col1:
            city_a = st.selectbox("City A", cities_list, key="a")
        with col2:
            city_b = st.selectbox("City B", cities_list, index=min(1, len(cities_list)-1), key="b")
        
        if city_a != city_b:
            result = compare_cities(city_summary, city_a, city_b)
            if result[0]:
                fig, da, db = result
                st.plotly_chart(fig, use_container_width=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"### {city_a}")
                    st.metric("m²", f"{da['median_m2']:.0f}")
                    st.metric("Price", f"€{da['median_price']:,.0f}")
                    st.metric("€/m²", f"€{da['median_price_per_m2']:,.0f}")
                with c2:
                    st.markdown(f"### {city_b}")
                    st.metric("m²", f"{db['median_m2']:.0f}")
                    st.metric("Price", f"€{db['median_price']:,.0f}")
                    st.metric("€/m²", f"€{db['median_price_per_m2']:,.0f}")
                ratio = da['median_m2'] / db['median_m2']
                st.info(f"**{ratio:.1f}x** more space in {city_a} for the same budget.")
        
        st.divider()
        
        # Methodology
        st.subheader("Data & Methodology")
        st.markdown(f"""
#### Source & Collection
- **Source:** Homestra.com public listings
- **Price range:** €200,000–€400,000
- **Property types:** Houses, apartments, townhouses
- **Total properties:** {len(properties_clean)}
- **Cities analyzed:** {len(city_summary)}

#### Processing
- **Deduplication:** Removed duplicate URLs
- **Validation:** Dropped listings with missing price, size, or city
- **Outliers:** Excluded unrealistic sizes (<10 m² or >5,000 m²)
- **Aggregation:** Used **median** (not mean) to resist outliers
- **Sample quality:** Cities with ≥{MIN_SAMPLE_SIZE} listings marked "sufficient"

#### Important Caveats
1. **Asking prices only** — not actual transaction prices
2. **Homestra coverage varies** — some regions have far fewer listings
3. **Not representative** — this is a sample from one platform at one point in time
4. **Potential duplicates** — same property may be listed multiple times or across platforms
5. **No mock data** — every property in this visualization is real and verifiable

**Use this for exploration and comparison, not as definitive market analysis.**
        """)
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}\n\nMake sure you've run `python scraper.py` first to collect Homestra listings.")

if __name__ == "__main__":
    main()
