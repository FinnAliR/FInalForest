import ee
import geemap
import tkinter as tk
from tkinter import ttk
import tempfile
import os
import webbrowser
try:
    ee.Authenticate()
except Exception as e:
    print(f"Authentication failed: {e}")
    exit(1)
# Initialize Earth Engine
def initialize_earth_engine():
    try:
        ee.Initialize(project='final-project-jpp317487')
        print("Earth Engine initialized successfully.")
        return True
    except Exception as e:
        print(f"Error initializing Earth Engine: {e}")
        return False

if not initialize_earth_engine():
    exit(1)

class MapViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Land Cover Classification")
        self.root.geometry("800x600")

        # Create control panel
        self.control_frame = ttk.Frame(root, padding="20")
        self.control_frame.pack(fill=tk.BOTH, expand=True)

        # Initialize map
        self.Map = geemap.Map()
        self.temp_html = tempfile.mktemp(suffix=".html")
        self.map_generated = False  # Track if map is ready to show

        # Add controls
        self.setup_controls()

    def setup_controls(self):
        """Setup control panel widgets"""
        # Title
        ttk.Label(
            self.control_frame,
            text="Land Cover Classification",
            font=('Helvetica', 16, 'bold')
        ).pack(pady=10)

        # Country selection
        ttk.Label(self.control_frame, text="Select Country:").pack(anchor='w', pady=(10,0))
        self.country_var = tk.StringVar(value="United Kingdom")
        ttk.Entry(self.control_frame, textvariable=self.country_var, width=30).pack()

        # Date range
        ttk.Label(self.control_frame, text="Start Date (YYYY-MM-DD):").pack(anchor='w', pady=(10,0))
        self.start_date_var = tk.StringVar(value="2022-01-01")
        ttk.Entry(self.control_frame, textvariable=self.start_date_var, width=30).pack()

        ttk.Label(self.control_frame, text="End Date (YYYY-MM-DD):").pack(anchor='w', pady=(10,0))
        self.end_date_var = tk.StringVar(value="2024-12-31")
        ttk.Entry(self.control_frame, textvariable=self.end_date_var, width=30).pack()

        # Run button
        ttk.Button(
            self.control_frame,
            text="Generate Land Cover Map",
            command=self.run_classification,
            style='Accent.TButton'
        ).pack(pady=20)

        # Status label
        self.status_var = tk.StringVar(value="Select parameters and click 'Generate'")
        ttk.Label(
            self.control_frame,
            textvariable=self.status_var,
            wraplength=400,
            foreground="#333333"
        ).pack()

        # Configure styles
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Helvetica', 12), padding=10, foreground='white')

    def show_map(self):
        """Show map in default browser only if processing is complete"""
        if self.map_generated:
            webbrowser.open(f"file://{self.temp_html}")
        else:
            self.status_var.set("Please generate the map first")

    def update_map_display(self):
        """Save the current map state"""
        self.Map.save(self.temp_html)
        self.map_generated = True

    def run_classification(self):
        """Run the classification process and show map when done"""
        self.status_var.set("Processing... Please wait")
        self.root.update()  # Force UI update

        try:
            country = self.country_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()

            # Clear previous layers
            self.Map.layers = [self.Map.layers[0]]  # Keep only base layer

            # Get ROI
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country))
            self.Map.addLayer(roi, {}, "Country Border")

            # Process Landsat data
            def applyScaleFactors(image):
                opticalBands = image.select('SR_B.').multiply(0.0000275).add(-0.2)
                thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0)
                return image.addBands(opticalBands, None, True).addBands(thermalBands, None, True)

            image = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterDate(start_date, end_date) \
                .filterBounds(roi) \
                .map(applyScaleFactors) \
                .sort('CLOUD_COVER') \
                .median()

            # Add visualization
            visualization = {'bands': ['SR_B4', 'SR_B3', 'SR_B2'], 'min': 0, 'max': 0.3}
            self.Map.addLayer(image, visualization, "Landsat True Colour")
            self.Map.centerObject(roi, 6)

            # Add land cover
            lc = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
                .filterDate(start_date, end_date) \
                .mosaic() \
                .remap([1, 2, 3, 5, 7, 8, 9, 10, 11], [1, 2, 3, 4, 5, 6, 7, 8, 9]) \
                .rename('lc')

            land_cover = lc.clip(roi.geometry())
            self.Map.addLayer(land_cover,
                            {'min': 1, 'max': 9, 'palette': dict['colors']},
                            'Land Cover')

            # Save and show map
            self.update_map_display()
            self.status_var.set("Processing complete! Opening map in browser...")
            self.root.update()
            self.show_map()

        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
            self.map_generated = False

# Land cover dictionary
dict = {
    "names": [
        "Water", "Trees", "Flooded Vegetation", "Crops",
        "Developed land", "Barren land", "Snow and ice",
        "Clouds", "Rangeland"
    ],
    "colors": [
        "#1A5BAB", "#358221", "#87D19E", "#FFDB5C",
        "#ED022A", "#EDE9E4", "#F2FAFF", "#C8C8C8",
        "#C6AD9D"
    ]
}

if __name__ == "__main__":
    root = tk.Tk()
    app = MapViewer(root)
    root.mainloop()