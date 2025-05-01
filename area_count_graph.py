import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from datetime import datetime

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
    """Reads an image and counts pixel areas per class."""
    img = Image.open(image_path)
    img_array = np.array(img)

    counts = {}
    for class_value, class_name in CLASS_MAPPING.items():
        pixel_count = np.sum(img_array == class_value)
        area_sqm = pixel_count * PIXEL_SIZE_SQ_M
        area_sqkm = area_sqm / 1e6  # Convert to square kilometers
        counts[class_name] = area_sqkm

    counts['Date'] = date_label
    return counts


def process_folder(folder_path):
    """Processes all images in a folder."""
    all_records = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".png") or filename.endswith(".tif"):
            try:
                date_str = filename.split('.')[0]  # expects 'YYYY-MM.png'
                try:
                    date_label = datetime.strptime(date_str, "%Y-%m")
                except ValueError:
                    date_label = datetime.strptime(date_str, "%Y")

                record = process_image(os.path.join(folder_path, filename), date_label)
                all_records.append(record)

            except Exception as e:
                print(f"[Warning] Skipping file {filename}: {e}")

    if not all_records:
        raise ValueError("No valid image records found in folder. Check filenames and format (e.g., 2023-01.png)")

    df = pd.DataFrame(all_records)

    if 'Date' not in df.columns:
        print("DEBUG: DataFrame columns:", df.columns)
        raise KeyError("'Date' column missing in DataFrame. Check filename format.")

    df = df.sort_values('Date')
    return df



def plot_area(df, time_group='month', save_path=None):
    """Plots area bar graphs over time, optionally saves the graph as an image."""
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