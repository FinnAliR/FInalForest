import ee
import pandas as pd
from classification_utils import build_custom_forest_image, build_esri_image

def compute_forest_area_time_series(
    country: str,
    years: list[int],
    use_custom: bool,
    log_fn=print,
    progress_fn=lambda v: None
) -> pd.DataFrame:
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country)).geometry()

    records = []
    total = len(years)

    for idx, year in enumerate(years):
        log_fn(f"Processing {year} using {'custom' if use_custom else 'ESRI'} model...")
        try:
            image = (
                build_custom_forest_image(year, roi) if use_custom
                else build_esri_image(year, roi)
            )

            # Sanity check class values
            hist = image.reduceRegion(
                reducer=ee.Reducer.frequencyHistogram(),
                geometry=roi,
                scale=30,
                maxPixels=1e9
            ).get('lc').getInfo()
            log_fn(f"[{year}] Class histogram: {hist}")

            forest_mask = image.eq(2)
            forest_area_image = forest_mask.multiply(ee.Image.pixelArea()).rename('forest_area')

            stats = forest_area_image.reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=roi,
                scale=10,
                maxPixels=1e13,
                bestEffort=True
            )

            result = stats.getInfo()
            area_sqm = result.get('forest_area', 0)
            log_fn(f"[{year}] Forest area: {area_sqm / 1e6:.2f} km²")

        except Exception as e:
            log_fn(f"[{year}] Error: {e}")
            area_sqm = 0

        records.append({'Year': year, 'Forest (sq.km)': area_sqm / 1e6})
        progress_fn((idx + 1) / total * 100)

    df = pd.DataFrame(records)
    df['Date'] = pd.to_datetime(df['Year'], format='%Y')
    return df.sort_values('Date')