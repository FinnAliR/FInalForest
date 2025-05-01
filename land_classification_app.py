import ee
import geemap
import tkinter as tk
from tkinter import ttk, messagebox
import tempfile
import os
from bs4 import BeautifulSoup
import threading
from tkinterweb import HtmlFrame
import subprocess

import sys
print(sys.executable)


try:
    ee.Authenticate()
except Exception as e:
    print(f"Authentication failed: {e}")
    exit(1)


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
        self.root.geometry("1200x800")  # Larger window for map display

        # Create main frames
        self.control_frame = ttk.Frame(root, width=300, padding="20")
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.map_frame = ttk.Frame(root)
        self.map_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Initialize map and HTML frame
        self.Map = geemap.Map()
        self.temp_html = tempfile.mktemp(suffix=".html")
        self.map_generated = False

        # Create HTML viewer
        self.html_view = HtmlFrame(self.map_frame)
        self.html_view.pack(fill=tk.BOTH, expand=True)

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
        ttk.Label(self.control_frame, text="Select Country:").pack(anchor='w', pady=(10, 0))
        self.country_var = tk.StringVar(value="United Kingdom")
        ttk.Entry(self.control_frame, textvariable=self.country_var, width=30).pack()

        # Date range
        ttk.Label(self.control_frame, text="Start Date (YYYY-MM-DD):").pack(anchor='w', pady=(10, 0))
        self.start_date_var = tk.StringVar(value="2022-01-01")
        ttk.Entry(self.control_frame, textvariable=self.start_date_var, width=30).pack()

        ttk.Label(self.control_frame, text="End Date (YYYY-MM-DD):").pack(anchor='w', pady=(10, 0))
        self.end_date_var = tk.StringVar(value="2024-12-31")
        ttk.Entry(self.control_frame, textvariable=self.end_date_var, width=30).pack()

        # Run button
        ttk.Button(
            self.control_frame,
            text="Generate Land Cover Map",
            command=self.run_classification,
            style='Accent.TButton'
        ).pack(pady=20)

        ttk.Button(
            self.control_frame,
            text="Generate Area Graph",
            command=self.generate_area_graph
        ).pack(pady=10)


        # Status label
        self.status_var = tk.StringVar(value="Select parameters and click 'Generate'")
        ttk.Label(
            self.control_frame,
            textvariable=self.status_var,
            wraplength=250,
            foreground="#333333"
        ).pack()

        # Configure styles
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Helvetica', 12), padding=10, foreground='white')

    # def update_map_display(self):
    #     """Save and display the map in the GUI"""
    #     self.Map.save(self.temp_html)
    #     self.map_generated = True
    #
    #     # Load the HTML file and display in HtmlFrame
    #     with open(self.temp_html, 'r', encoding='utf-8') as f:
    #         html_content = f.read()
    #
    #     # Use BeautifulSoup to modify if needed
    #     soup = BeautifulSoup(html_content, 'html.parser')
    #
    #     # You can modify the HTML here if needed
    #     # For example, adjust the map container size:
    #     map_div = soup.find('div', {'id': 'map'})
    #     if map_div:
    #         map_div['style'] = 'width: 100%; height: 100%;'
    #
    #     self.html_view.load_html(str(soup))
    #     self.status_var.set("Processing complete!")

    def update_map_display(self):
        """Save and display the map in the GUI"""
        self.Map.save(self.temp_html)
        print(f"Map saved to: {self.temp_html}")  # Debug print

        # Verify file exists
        if os.path.exists(self.temp_html):
            print("HTML file exists")  # Debug print
            with open(self.temp_html, 'r') as f:
                print(f"File size: {len(f.read())} bytes")  # Debug print
        else:
            print("HTML file NOT created!")  # Debug print
            return

        self.map_generated = True
        self.html_view.load_html(self.temp_html)

    def run_classification(self):
        """Run the classification process in a thread"""
        self.status_var.set("Processing... Please wait")
        self.root.update()

        # Run in a thread to prevent GUI freezing
        threading.Thread(target=self._run_classification_task, daemon=True).start()

    def _run_classification_task(self):
        """The actual classification task"""
        try:
            country = self.country_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()

            # Clear previous layers
            self.Map.layers = [self.Map.layers[0]]

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

            # Update GUI from the main thread
            self.root.after(0, self.update_map_display)

        except Exception as error:
            # Capture the error in the lambda's closure
            self.root.after(0, lambda err=error: self.status_var.set(f"Error: {str(err)}"))
            self.map_generated = False

    def generate_area_graph(self):
        try:
            script_path = os.path.join(os.path.dirname(__file__), "area_count_graph.py")
            subprocess.run([sys.executable, script_path], check=True)
            messagebox.showinfo("Success", "Area graph generated and saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate area graph:\n{str(e)}")

# Land cover dictionary (must be before class if referenced in methods)
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