import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from datetime import datetime
import rasterio

# Configuration
PIXEL_SIZE_SQ_M = 100  # Example: 10m x 10m resolution = 100 square meters per pixel
CLASS_MAPPING = {
    2: 'Trees',
}


# ------------- FUNCTIONS ----------------

import sys

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


def process_folder(folder_path, progress_callback=None):
    from collections import defaultdict
    import re

    grouped = defaultdict(list)
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".tif", ".tiff", ".png"))]
    total_files = len(files)

    for idx, filename in enumerate(files):
        matches = re.findall(r'(20\d{2})', filename)
        year = None
        for m in matches:
            y = int(m)
            if 2017 <= y <= 2025:
                year = y
                break
        if not year:
            print(f"[Skipped] No valid year found in: {filename}")
            continue
        date_label = datetime(year, 1, 1)
        image_path = os.path.join(folder_path, filename)
        record = process_image(image_path, date_label)
        grouped[date_label].append(record)
        if progress_callback:
            progress_callback((idx + 1) / total_files * 50)  # scale to 0-50%

    # Aggregate all forest areas per year
    merged = []
    for date_label, records in grouped.items():
        total_forest = sum(r['Forest'] for r in records)
        merged.append({'Date': date_label, 'Forest': total_forest})

    df = pd.DataFrame(merged)
    df = df.sort_values('Date')
    return df

def generate_graph(df):
    return plot_forest_graph(df)

def plot_forest_graph(df):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df['Date'], df['Forest'], marker='o', label='Forest Cover (sq.km)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Forest Area (sq.km)')
    ax.set_title('Forest Cover Over Time')
    ax.legend()
    ax.grid(True)
    return fig
# ------------- MAIN USAGE ----------------

if __name__ == "__main__":
    #Folder containing maps
    folder = "./classified_maps"

    # Process all images
    df_areas = process_folder(folder)

    # Optional: Save to CSV
    df_areas.to_csv("land_cover_areas.csv", index=False)