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
        fileFormat='GeoTIFF'
    )
    task.start()
    return task

def export_monthly_landcover(country_name, start_date_str, end_date_str, project_id='final-project-jpp317487'):
    """
    Batch export of land cover images per month to Google Drive.
    Date format: YYYY-MM-DD
    """
    ee.Initialize(project=project_id)
    countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    roi = countries.filter(ee.Filter.eq("country_na", country_name))

    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")

    current = start
    tasks = []
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_str = current.strftime("%Y-%m")

        lc = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
            .filterDate(current.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d")) \
            .mosaic() \
            .remap([1, 2, 3, 5, 7, 8, 9, 10, 11], [1, 2, 3, 4, 5, 6, 7, 8, 9]) \
            .rename('lc')

        filename = f"land_cover_{country_name.replace(' ', '_')}_{month_str}"
        task = export_image_to_drive(lc, roi.geometry(), filename)
        tasks.append((month_str, task.id))

        current = next_month

    print(f"Started {len(tasks)} export tasks.")
    return tasks