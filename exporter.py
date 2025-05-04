import ee
from datetime import datetime, timedelta

def export_image_to_drive(image, region, filename_prefix, folder='EarthEngineExports', scale=10):
    task = ee.batch.Export.image.toDrive(
        image=image.clip(region),
        description=f'Export_{filename_prefix}',
        folder=folder,
        fileNamePrefix=filename_prefix,
        region=region,
        scale=scale,
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    task.start()
    return task

def export_yearly_landcover(country_name, start_date_str, end_date_str, project_id='final-project-jpp317487'):
    """
    Batch export of land cover images per year to Google Drive.
    Date format: YYYY-MM-DD
    """
    ee.Initialize(project=project_id)
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country_name))

    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")

    # Create a unique folder name with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    export_folder = f"LandCoverExports_{timestamp}"

    current = start
    tasks = []
    while current.year <= end.year:
        year_start = datetime(current.year, 1, 1)
        year_end = datetime(current.year + 1, 1, 1)
        label = str(current.year)

        collection = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
            .filterDate(year_start.strftime("%Y-%m-%d"), year_end.strftime("%Y-%m-%d"))

        if collection.size().getInfo() == 0:
            print(f"[Skipped] No landcover data for {year_start}")
        else:
            lc = collection.mosaic() \
                .remap([1, 2, 3, 5, 7, 8, 9, 10, 11], [1, 2, 3, 4, 5, 6, 7, 8, 9]) \
                .rename('lc')

            filename = f"land_cover_{country_name.replace(' ', '_')}_{year_start}"
            task = export_image_to_drive(lc, roi.geometry(), filename, folder=export_folder)
            tasks.append((year_start, task.id))

        current = datetime(current.year + 1, 1, 1)

    print(f"Started {len(tasks)} export tasks in folder '{export_folder}'.")
    return tasks
