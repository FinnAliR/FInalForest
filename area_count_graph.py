import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from datetime import datetime
import rasterio
import re
from collections import defaultdict

# Configuration
PIXEL_SIZE_SQ_M = 100  # Example: 10m x 10m resolution = 100 square meters per pixel
CLASS_MAPPING = {
    1: 'Water',
    2: 'Trees',
    3: 'Flooded Vegetation',
    4: 'Crops',
    5: 'Developed land',
    6: 'Barren land',
    7: 'Snow and ice',
    8: 'Clouds',
    9: 'Rangeland'
}


# ------------- FUNCTIONS ----------------

import sys
print(sys.executable)

def process_image(image_path, date_label):
    ext = os.path.splitext(image_path)[1].lower()

    if ext in [".tif", ".tiff"]:
        with rasterio.open(image_path) as src:
            img_array = src.read(1)
    else:
        img = Image.open(image_path)
        img_array = np.array(img)

    # Forest class is 2
    forest_pixel_count = np.sum(img_array == 2)
    area_sqm = forest_pixel_count * PIXEL_SIZE_SQ_M
    area_sqkm = area_sqm / 1e6

    return {'Date': date_label, 'Forest': area_sqkm}


def process_folder(folder_path):
    from collections import defaultdict
    import re

    grouped = defaultdict(list)

    for filename in os.listdir(folder_path):
        if filename.lower().endswith((".tif", ".tiff", ".png")):
            match = re.search(r'(\d{4})', filename)
            if not match:
                continue
            year = int(match.group(1))
            date_label = datetime(year, 1, 1)
            image_path = os.path.join(folder_path, filename)
            record = process_image(image_path, date_label)
            grouped[date_label].append(record)

    # Aggregate all forest areas per year
    merged = []
    for date_label, records in grouped.items():
        total_forest = sum(r['Forest'] for r in records)
        merged.append({'Date': date_label, 'Forest': total_forest})

    df = pd.DataFrame(merged)
    df = df.sort_values('Date')
    return df

def generate_graph(df, forest_only=False):
    if forest_only:
        return plot_forest_graph(df)
    else:
        return plot_area(df)

def plot_forest_graph(df):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df['Date'], df['Forest'], marker='o', label='Forest Cover (sq.km)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Forest Area (sq.km)')
    ax.set_title('Forest Cover Over Time')
    ax.legend()
    ax.grid(True)
    return fig

def plot_area(df, time_group='month', save_path=None):
    df_plot = df.copy()

    if time_group == 'year':
        df_plot['Year'] = df_plot['Date'].dt.year
        group = df_plot.groupby('Year').sum()
    elif time_group == 'month':
        df_plot['Month'] = df_plot['Date'].dt.to_period('M')
        group = df_plot.groupby('Month').sum()
    else:
        raise ValueError("time_group must be 'month' or 'year'")

    group.drop(columns=['Date'], errors='ignore', inplace=True)

    # Plotting
    ax = group.plot(kind='bar', stacked=True, figsize=(14, 8))
    plt.ylabel('Area (sq km)')
    plt.title(f'Land Cover Area over Time (by {time_group})')
    plt.legend(title='Land Cover Class')
    plt.grid(axis='y')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Graph saved to {save_path}")

    plt.show()


# ------------- MAIN USAGE ----------------

if __name__ == "__main__":
    # Example: Folder containing classified maps (e.g., '2023-01.png', '2023-02.png', ...)
    folder = "./classified_maps"

    # Process all images
    df_areas = process_folder(folder)

    # Optional: Save to CSV
    df_areas.to_csv("land_cover_areas.csv", index=False)

    # Plot by month and save
    plot_area(df_areas, time_group='month', save_path="land_cover_area_graph.png")

    # Plot by year (alternative)
    # plot_area(df_areas, time_group='year', save_path="land_cover_area_yearly.png")