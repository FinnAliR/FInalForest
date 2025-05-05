# earth_engine_graph.py
import ee
import pandas as pd

from classification_utils import build_custom_forest_image, build_esri_image


def compute_forest_area_time_series(country: str, years: list[int], use_custom: bool) -> pd.DataFrame:
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country)).geometry()

    records = []

    for year in years:
        image = (
            build_custom_forest_image(year, roi) if use_custom
            else build_esri_image(year, roi)
        )
        forest_mask = image.eq(2)  # Forest class is 2
        forest_area = forest_mask.multiply(ee.Image.pixelArea())

        stats = forest_area.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=10,
            maxPixels=1e13
        )
        area_sqm = stats.getInfo().get('lc', 0)
        records.append({'Year': year, 'Forest (sq.km)': area_sqm / 1e6})

    df = pd.DataFrame(records)
    return df.sort_values('Year')