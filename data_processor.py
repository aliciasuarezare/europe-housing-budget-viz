import os
import pandas as pd


class DataCleaner:
    def __init__(self, raw_csv_path="data/homestra_properties_raw.csv"):
        self.raw_csv_path = raw_csv_path
        self.df = pd.DataFrame()
        self.df_clean = pd.DataFrame()

    def load_raw_data(self):
        if not os.path.exists(self.raw_csv_path):
            print(f"Warning: {self.raw_csv_path} not found")
            return self.df
        self.df = pd.read_csv(self.raw_csv_path)
        print(f"Loaded {len(self.df)} raw properties")
        return self.df

    def clean_data(self):
        if self.df.empty:
            self.load_raw_data()
        if self.df.empty:
            return self.df_clean

        df = self.df.copy()
        required = ["price_eur", "size_m2", "city"]
        df = df.dropna(subset=required)
        for column in ["price_eur", "size_m2", "bedrooms", "bathrooms"]:
            if column in df:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=["price_eur", "size_m2"])
        df = df[df["price_eur"].between(200_000, 400_000)]
        df = df[df["size_m2"].between(10, 5_000)]
        df["city"] = df["city"].astype(str).str.strip().str.title()
        df["price_per_m2"] = (df["price_eur"] / df["size_m2"]).round(2)
        if "listing_url" in df:
            df = df.drop_duplicates(subset=["listing_url"], keep="first")
        self.df_clean = df.reset_index(drop=True)
        print(f"Cleaned data: {len(self.df_clean)} properties")
        return self.df_clean

    def save_clean_data(self, output_path="data/homestra_properties_clean.csv"):
        if self.df_clean.empty:
            self.clean_data()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.df_clean.to_csv(output_path, index=False)
        return output_path

    def get_data_quality_report(self):
        if self.df_clean.empty:
            self.clean_data()
        return {
            "total_properties": len(self.df_clean),
            "unique_cities": self.df_clean["city"].nunique() if not self.df_clean.empty else 0,
            "properties_with_bedrooms": int(self.df_clean["bedrooms"].notna().sum()) if "bedrooms" in self.df_clean else 0,
            "properties_with_listing_url": int(self.df_clean["listing_url"].notna().sum()) if "listing_url" in self.df_clean else 0,
        }


class CityAggregator:
    def __init__(self, clean_csv_path="data/homestra_properties_clean.csv"):
        self.clean_csv_path = clean_csv_path
        self.df = pd.DataFrame()
        self.city_summary = pd.DataFrame()

    def load_clean_data(self):
        if os.path.exists(self.clean_csv_path):
            self.df = pd.read_csv(self.clean_csv_path)
        return self.df

    def aggregate_by_city(self, min_sample_size=5):
        if self.df.empty:
            self.load_clean_data()
        if self.df.empty:
            return self.city_summary

        grouped = self.df.groupby("city", dropna=False)
        summary = grouped.agg(
            n_listings=("city", "size"),
            median_price=("price_eur", "median"),
            median_m2=("size_m2", "median"),
            median_price_per_m2=("price_per_m2", "median"),
            min_m2=("size_m2", "min"),
            max_m2=("size_m2", "max"),
            median_bedrooms=("bedrooms", "median"),
            country=("country", "first"),
            is_capital=("is_capital", "first"),
        ).reset_index()
        summary["sample_quality"] = summary["n_listings"].apply(
            lambda n: "Sufficient sample" if n >= min_sample_size else "Limited sample"
        )
        self.city_summary = summary.sort_values("median_m2", ascending=False).reset_index(drop=True)
        return self.city_summary

    def save_city_summary(self, output_path="data/cities_summary.csv"):
        if self.city_summary.empty:
            self.aggregate_by_city()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.city_summary.to_csv(output_path, index=False)
        return output_path


def run_full_pipeline():
    cleaner = DataCleaner()
    cleaner.load_raw_data()
    cleaner.clean_data()
    cleaner.save_clean_data()
    aggregator = CityAggregator()
    aggregator.load_clean_data()
    aggregator.aggregate_by_city()
    aggregator.save_city_summary()


if __name__ == "__main__":
    run_full_pipeline()
