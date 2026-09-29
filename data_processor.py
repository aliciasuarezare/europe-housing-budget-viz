import pandas as pd
import numpy as np
from datetime import datetime
import os

class DataCleaner:
    def __init__(self, raw_csv_path='data/homestra_properties_raw.csv'):
        self.raw_csv_path = raw_csv_path
        self.df = None
        self.df_clean = None
        
    def load_raw_data(self):
        """Load raw scraped data"""
        if not os.path.exists(self.raw_csv_path):
            print(f"Warning: {self.raw_csv_path} not found")
            return pd.DataFrame()
        
        self.df = pd.read_csv(self.raw_csv_path)
        print(f"Loaded {len(self.df)} raw properties")
        return self.df
    
    def clean_data(self):
        """Clean and validate property data"""
        if self.df is None:
            self.load_raw_data()
        
        if self.df.empty:
            self.df_clean = pd.DataFrame()
            return self.df_clean
        
        df = self.df.copy()
        
        # Remove rows with missing critical fields
        df = df.dropna(subset=['price_eur', 'size_m2', 'city'])
        
        # Remove properties outside price range
        df = df[(df['price_eur'] >= 200000) & (df['price_eur'] <= 400000)]
        
        # Remove properties with unrealistic sizes
        df = df[(df['size_m2'] > 10) & (df['size_m2'] < 5000)]
        
        # Recalculate price per m² to ensure accuracy
        df['price_per_m2'] = (df['price_eur'] / df['size_m2']).round(2)
        
        # Remove duplicate listings (same URL or same price/size combo in same city within 1 day)
        df = df.drop_duplicates(subset=['listing_url'], keep='first')
        
        # Ensure data types are correct
        df['price_eur'] = df['price_eur'].astype(float)
        df['size_m2'] = df['size_m2'].astype(float)
        df['price_per_m2'] = df['price_per_m2'].astype(float)
        df['bedrooms'] = pd.to_numeric(df['bedrooms'], errors='coerce')
        df['bathrooms'] = pd.to_numeric(df['bathrooms'], errors='coerce')
        
        # Standardize city names (remove extra whitespace, fix capitalization)
        df['city'] = df['city'].str.strip().str.title()
        
        self.df_clean = df
        print(f"Cleaned data: {len(df)} properties remaining after validation")
        
        return self.df_clean
    
    def get_data_quality_report(self):
        """Generate data quality report"""
        if self.df_clean is None:
            self.clean_data()
        
        df = self.df_clean
        
        report = {
            'total_properties': len(df),
            'unique_cities': df['city'].nunique(),
            'price_range': (df['price_eur'].min(), df['price_eur'].max()),
            'size_range': (df['size_m2'].min(), df['size_m2'].max()),
            'properties_with_bedrooms': df['bedrooms'].notna().sum(),
            'properties_with_bathrooms': df['bathrooms'].notna().sum(),
            'properties_with_listing_url': df['listing_url'].notna().sum(),
            'countries': df['country'].nunique()
        }
        
        return report
    
    def save_clean_data(self, output_path='data/homestra_properties_clean.csv'):
        """Save cleaned data to CSV"""
        if self.df_clean is None:
            self.clean_data()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.df_clean.to_csv(output_path, index=False)
        print(f"Saved cleaned data to {output_path}")
        
        return output_path


class CityAggregator:
    def __init__(self, clean_csv_path='data/homestra_properties_clean.csv'):
        self.clean_csv_path = clean_csv_path
        self.df = None
        self.city_summary = None
        
    def load_clean_data(self):
        """Load cleaned property data"""
        if not os.path.exists(self.clean_csv_path):
            print(f"Error: {self.clean_csv_path} not found. Run DataCleaner first.")
            return pd.DataFrame()
        
        self.df = pd.read_csv(self.clean_csv_path)
        print(f"Loaded {len(self.df)} clean properties")
        return self.df
    
    def aggregate_by_city(self, min_sample_size=5):
        """Aggregate data at city level"""
        if self.df is None:
            self.load_clean_data()
        
        if self.df.empty:
            self.city_summary = pd.DataFrame()
            return self.city_summary
        
        city_stats = self.df.groupby('city').agg({
            'price_eur': ['median', 'min', 'max', 'count'],
            'size_m2': ['median', 'min', 'max'],
            'price_per_m2': 'median',
            'bedrooms': 'median',
            'country': 'first',
            'is_capital': 'first'
        }).round(2)
        
        # Flatten column names
        city_stats.columns = ['_'.join(col).strip() for col in city_stats.columns.values]
        city_stats = city_stats.rename(columns={
            'price_eur_median': 'median_price',
            'price_eur_min': 'min_price',
            'price_eur_max': 'max_price',
            'price_eur_count': 'n_listings',
            'size_m2_median': 'median_m2',
            'size_m2_min': 'min_m2',
            'size_m2_max': 'max_m2',
            'price_per_m2_median': 'median_price_per_m2',
            'bedrooms_median': 'median_bedrooms',
            'country_first': 'country',
            'is_capital_first': 'is_capital'
        })
        
        # Add sample quality indicator
        city_stats['sample_quality'] = city_stats['n_listings'].apply(
            lambda x: 'Good' if x >= min_sample_size else 'Limited'
        )
        
        # Reset index to make city a column
        city_stats = city_stats.reset_index()
        
        # Sort by median price per m²
        city_stats = city_stats.sort_values('median_price_per_m2').reset_index(drop=True)
        
        self.city_summary = city_stats
        print(f"Aggregated data for {len(city_stats)} cities")
        
        return self.city_summary
    
    def get_city_sample_info(self):
        """Get information about sample sizes by city"""
        if self.city_summary is None:
            self.aggregate_by_city()
        
        return self.city_summary[['city', 'country', 'n_listings', 'sample_quality']]
    
    def save_city_summary(self, output_path='data/cities_summary.csv'):
        """Save city-level summary to CSV"""
        if self.city_summary is None:
            self.aggregate_by_city()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.city_summary.to_csv(output_path, index=False)
        print(f"Saved city summary to {output_path}")
        
        return output_path
    
    def get_statistics(self):
        """Get overall statistics"""
        if self.df is None:
            self.load_clean_data()
        
        if self.df.empty:
            return {}
        
        stats = {
            'total_properties': len(self.df),
            'total_cities': self.df['city'].nunique(),
            'median_price': self.df['price_eur'].median(),
            'median_m2': self.df['size_m2'].median(),
            'median_price_per_m2': self.df['price_per_m2'].median(),
            'most_space_city': self._get_most_space_city(),
            'least_space_city': self._get_least_space_city(),
        }
        
        return stats
    
    def _get_most_space_city(self):
        """Find city with most space for median price"""
        if self.city_summary is None:
            self.aggregate_by_city()
        
        if self.city_summary.empty:
            return None
        
        idx = self.city_summary['median_m2'].idxmax()
        return self.city_summary.loc[idx, 'city']
    
    def _get_least_space_city(self):
        """Find city with least space for median price"""
        if self.city_summary is None:
            self.aggregate_by_city()
        
        if self.city_summary.empty:
            return None
        
        idx = self.city_summary['median_m2'].idxmin()
        return self.city_summary.loc[idx, 'city']


def run_full_pipeline():
    """Execute complete data processing pipeline"""
    print("=" * 60)
    print("HOUSING DATA PROCESSING PIPELINE")
    print("=" * 60)
    
    # Clean raw data
    print("\n1. CLEANING DATA...")
    cleaner = DataCleaner()
    cleaner.load_raw_data()
    cleaner.clean_data()
    cleaner.save_clean_data()
    
    report = cleaner.get_data_quality_report()
    print(f"\nData Quality Report:")
    for key, value in report.items():
        print(f"  {key}: {value}")
    
    # Aggregate by city
    print("\n2. AGGREGATING BY CITY...")
    aggregator = CityAggregator()
    aggregator.load_clean_data()
    aggregator.aggregate_by_city()
    aggregator.save_city_summary()
    
    print(f"\nCity Summary (top 5 by price per m²):")
    print(aggregator.city_summary[['city', 'country', 'n_listings', 'median_m2', 'median_price']].head())
    
    stats = aggregator.get_statistics()
    print(f"\nOverall Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_full_pipeline()
