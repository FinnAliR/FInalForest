import ee
from datetime import datetime
import matplotlib.pyplot as plt

def run_ndvi_analysis(country_name, start_year, end_year, log_fn, progress_fn, display_frame):
    """
    Compute and display mean annual NDVI time series for a country.
    - country_name: e.g. "United Kingdom"
    - start_year, end_year: ints
    - log_fn(str): to append status messages
    - progress_fn(float 0–100): to update a progress bar
    - display_frame: a tk.Frame (or similar) to draw the chart into
    """
    # Build ROI
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country_name)).geometry()

    ndvi_results = {}
    total = end_year - start_year + 1
    for idx, year in enumerate(range(start_year, end_year + 1)):
        log_fn(f"Processing NDVI for {year}...")
        # Pick dataset
        dataset = 'LANDSAT/LC08/C02/T1_L2' if year < 2021 else 'LANDSAT/LC09/C02/T1_L2'
        start = f"{year}-01-01"; end = f"{year}-12-31"
        col = (ee.ImageCollection(dataset)
                 .filterDate(start, end)
                 .filterBounds(roi)
                 .map(lambda img: img.normalizedDifference(['SR_B5','SR_B4']).rename('NDVI')))
        ndvi_img = col.mean()
        # Mean NDVI over ROI
        mean_ndvi = ndvi_img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=500,
            maxPixels=1e9
        ).get('NDVI').getInfo()
        ndvi_results[year] = mean_ndvi
        progress_fn((idx+1)/total*100)

    # Plot in display_frame
    years, values = zip(*sorted(ndvi_results.items()))
    fig, ax = plt.subplots(figsize=(8,5))
    ax.plot(years, values, marker='o')
    ax.set_title(f"Mean NDVI {start_year}–{end_year}\n{country_name}")
    ax.set_xlabel("Year"); ax.set_ylabel("NDVI"); ax.grid(True)
    # embed into tkinter
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    for w in display_frame.winfo_children(): w.destroy()
    canvas = FigureCanvasTkAgg(fig, master=display_frame)
    canvas.draw(); canvas.get_tk_widget().pack(fill='both', expand=True)

    log_fn("NDVI analysis complete.")
    progress_fn(100)
