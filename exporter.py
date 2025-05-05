import time

import ee
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import classification_utils
from classification_utils import build_custom_forest_image, build_esri_image

# Export to Google Drive

def export_yearly_landcover(
    country_name: str,
    start_date_str: str,
    end_date_str: str,
    project_id: str = 'final-project-jpp317487',
    folder_root: str = 'LandCoverExports',
    scale: int = 10,
    tile_size_deg: float = 0.5,
    max_pixels: float = 50e6,   # adjust this threshold to taste
    log_fn=print,
    progress_fn=lambda v: None,
    cancel_event=None
):
    """
    Export one tile per year if small enough, otherwise subdivide into degree-tiles.
    """
    ee.Initialize(project=project_id)
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country_name)).geometry()

    # 1) Estimate total pixel count
    area_m2 = roi.area().getInfo()
    pixel_count = area_m2 / (scale * scale)
    log_fn(f"→ Region ≈ {area_m2:,.0f} m² → ~{pixel_count:,.0f} px @ {scale} m")

    # 2) Prepare output folder
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    export_folder = f"{folder_root}_{country_name.replace(' ','_')}_{ts}"
    os.makedirs(export_folder, exist_ok=True)

    # 3) Build the list of years
    start_year = int(start_date_str[:4])
    end_year   = int(end_date_str[:4])
    years = range(start_year, end_year + 1)

    tasks = []

    # 4a) If it’s “small,” just fire one big export per year
    for year in years:
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01" if year < end_year else f"{end_year + 1}-01-01"

        coll = (ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS')
                .filterDate(year_start, year_end))
        if coll.size().getInfo() == 0:
            log_fn(f"[Skipped] no data for {year}")
            continue

        img = (coll
               .mosaic()
               .remap([1, 2, 3, 5, 7, 8, 9, 10, 11], [1, 2, 3, 4, 5, 6, 7, 8, 9])
               .rename('lc'))

        prefix = f"{country_name.replace(' ', '_')}_{year}"
        task = ee.batch.Export.image.toDrive(
            image=img.clip(roi),
            description=f"Export_{prefix}",
            folder=export_folder,
            fileNamePrefix=prefix,
            region=roi,
            scale=scale,
            maxPixels=1e13,  # still capped, but single request
            fileFormat='GeoTIFF'
        )
        task.start()
        tasks.append((year, 0, 0, task.id))
    return tasks


def export_local_yearly_landcover(
    country_name: str,
    start_date_str: str,
    end_date_str: str,
    output_folder: str,
    tile_size_deg: float = 0.5,
    scale: int = 10,
    use_custom: bool = False,
    log_fn=print,
    progress_fn=lambda v: None,
    cancel_event=None                    # ← New argument
):
    log_fn(f"Starting local export: {start_date_str} to {end_date_str}, custom={use_custom}")

    # Load ROI
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country_name)).geometry()
    bounds = roi.bounds().getInfo()['coordinates'][0]
    lons = [pt[0] for pt in bounds]
    lats = [pt[1] for pt in bounds]
    minx, maxx = min(lons), max(lons)
    miny, maxy = min(lats), max(lats)

    # Build tile grid
    x_tiles = int((maxx - minx) / tile_size_deg) + 1
    y_tiles = int((maxy - miny) / tile_size_deg) + 1
    tiles = [{'i': i, 'j': j} for i in range(x_tiles) for j in range(y_tiles)]

    # Build list of years
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_dt   = datetime.strptime(end_date_str, "%Y-%m-%d")
    years = list(range(start_dt.year, end_dt.year + 1))
    total_steps = len(years) * len(tiles)
    step = 0

    os.makedirs(output_folder, exist_ok=True)

    def download_tile(image, year, tile, max_retries=3):
        nonlocal step
        # Honor cancel
        if cancel_event and cancel_event.is_set():
            return

        i, j = tile['i'], tile['j']
        xmin = minx + i * tile_size_deg
        ymin = miny + j * tile_size_deg
        xmax = xmin + tile_size_deg
        ymax = ymin + tile_size_deg
        coords = [xmin, ymin, xmax, ymax]

        clipped = image.clip(roi)
        try:
            url = clipped.getDownloadURL({
                'region': coords,
                'scale': scale,
                'format': 'GeoTIFF',
                'maxPixels': 1e13           # ← Bump Earth Engine limit
            })
        except Exception as e:
            log_fn(f"[Error] Year {year} tile ({i},{j}): {e}")
            return

        path = os.path.join(output_folder, f"lc_{year}_tile_{i}_{j}.tif")
        try:
            r = requests.get(url)
            r.raise_for_status()
            with open(path, 'wb') as f:
                f.write(r.content)
            log_fn(f"Saved {path}")
        except Exception as e:
            log_fn(f"[Error] {path}: {e}")

        step += 1
        progress_fn((step / total_steps) * 100)

    with ThreadPoolExecutor(max_workers=5) as executor:
        for year in years:
            # Honor cancel before each year
            if cancel_event and cancel_event.is_set():
                log_fn(f"⚠️ Local export canceled before building year {year}")
                break

            log_fn(f"Building classification for {year}.")
            try:
                if use_custom:
                    image = build_custom_forest_image(year, roi).rename('lc')
                else:
                    image = build_esri_image(year, roi).rename('lc')
            except Exception as e:
                log_fn(f"[Skipped] Build failed for {year}: {e}")
                step += len(tiles)
                progress_fn((step / total_steps) * 100)
                continue

            futures = [executor.submit(download_tile, image, year, tile) for tile in tiles]
            for f in futures:
                f.result()

    log_fn("Local export complete.")
    progress_fn(100)