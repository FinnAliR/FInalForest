import ee


def select_landsat_collection(year: int) -> str:
    if year < 2013:
        return 'LANDSAT/LE07/C02/T1_L2'
    elif year < 2021:
        return 'LANDSAT/LC08/C02/T1_L2'
    else:
        return 'LANDSAT/LC09/C02/T1_L2'


def build_esri_image(year: int, roi: ee.Geometry) -> ee.Image:
    """
    Fetch and remap the ESRI Global LULC dataset for the given year clipped to the ROI.
    """
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    collection = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
        .filterDate(start, end)
    # Remap to 1..9 classes and rename
    return (collection
            .mosaic()
            .remap([1,2,4,5,7,8,9,10,11], [1,2,3,4,5,6,7,8,9])
            .rename('lc'))


def build_custom_forest_image(year: int, roi: ee.Geometry) -> ee.Image:
    """
    Train a simple CART classifier on NDVI thresholds to separate forest vs non-forest for a given year,
    then classify and return a single-band image where 2 indicates forest and 1 non-forest.
    """
    # 1) Select and composite median
    collection_id = select_landsat_collection(year)
    composite = (ee.ImageCollection(collection_id)
                 .filterDate(f"{year}-01-01", f"{year}-12-31")
                 .filterBounds(roi)
                 .median())
    # 2) Compute NDVI and define masks
    ndvi = composite.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
    forest_mask = ndvi.gte(0.35)
    nonforest_mask = ndvi.lte(0.15)
    # 3) Prepare training data
    bands = ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7']
    features = composite.select(bands).addBands(ndvi)
    forest_samples = (features.updateMask(forest_mask)
                      .addBands(ee.Image.constant(1).rename('class'))
                      .sample(region=roi, scale=30, numPixels=2000))
    nonforest_samples = (features.updateMask(nonforest_mask)
                         .addBands(ee.Image.constant(0).rename('class'))
                         .sample(region=roi, scale=30, numPixels=2000))
    samples = forest_samples.merge(nonforest_samples)
    # 4) Ensure both classes exist
    class_vals = samples.aggregate_array('class').distinct().getInfo()
    if len(class_vals) < 2:
        raise ValueError(f"Only one class in training samples for year {year}")
    # 5) Train classifier and classify
    clf = ee.Classifier.smileCart().train(
        features=samples,
        classProperty='class',
        inputProperties=features.bandNames().getInfo()
    )
    classified = features.classify(clf)
    # Remap 0->1 non-forest, 1->2 forest
    return classified.add(1).toByte().rename('lc')