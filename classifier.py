import ee
import geemap
import os
import tempfile
from tkinter import ttk, messagebox
from tkinterweb import HtmlFrame
import threading

try:
    ee.Initialize(project='final-project-jpp317487')
except Exception as e:
    ee.Authenticate()
    ee.Initialize(project='final-project-jpp317487')

class ClassificationApp:
    def __init__(self, control_frame, display_frame, log_callback=None):
        self.control_frame = control_frame
        self.display_frame = display_frame
        self.log = log_callback if log_callback else print
        self.map = geemap.Map()
        self.temp_html = tempfile.mktemp(suffix=".html")

        self._setup_controls()
        self._setup_map()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Land Classification", font=("Helvetica", 16, "bold")).pack(pady=10)

        ttk.Label(self.control_frame, text="Country:").pack(anchor='w')
        self.country_var = ttk.Entry(self.control_frame)
        self.country_var.insert(0, "United Kingdom")
        self.country_var.pack()

        ttk.Label(self.control_frame, text="Start Date (YYYY-MM-DD):").pack(anchor='w')
        self.start_date = ttk.Entry(self.control_frame)
        self.start_date.insert(0, "2022-01-01")
        self.start_date.pack()

        ttk.Label(self.control_frame, text="End Date (YYYY-MM-DD):").pack(anchor='w')
        self.end_date = ttk.Entry(self.control_frame)
        self.end_date.insert(0, "2024-12-31")
        self.end_date.pack()

        ttk.Button(self.control_frame, text="Run Classification", command=self.run_classification).pack(pady=10)

    def _setup_map(self):
        self.html_view = HtmlFrame(self.display_frame)
        self.html_view.pack(fill='both', expand=True)

    def run_classification(self):
        threading.Thread(target=self._run_task, daemon=True).start()

    def _run_task(self):
        try:
            country = self.country_var.get()
            start_date = self.start_date.get()
            end_date = self.end_date.get()

            self.map.layers = [self.map.layers[0]]

            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country))
            self.map.addLayer(roi, {}, "Border")

            image = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
                .filterDate(start_date, end_date) \
                .filterBounds(roi) \
                .median()

            vis = {'bands': ['SR_B4', 'SR_B3', 'SR_B2'], 'min': 0, 'max': 0.3}
            self.map.addLayer(image, vis, 'Landsat RGB')
            self.map.centerObject(roi, 6)

            lc = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
                .filterDate(start_date, end_date) \
                .mosaic() \
                .remap([1, 2, 3, 5, 7, 8, 9, 10, 11], [1, 2, 3, 4, 5, 6, 7, 8, 9]) \
                .rename('lc')

            land_cover = lc.clip(roi.geometry())
            self.map.addLayer(land_cover,
                              {'min': 1, 'max': 9, 'palette': ["#1A5BAB", "#358221", "#87D19E", "#FFDB5C",
                                                              "#ED022A", "#EDE9E4", "#F2FAFF", "#C8C8C8",
                                                              "#C6AD9D"]},
                              'Land Cover')

            self.map.save(self.temp_html)
            self.html_view.load_html(self.temp_html)

        except Exception as e:
            messagebox.showerror("Classification Error", str(e))