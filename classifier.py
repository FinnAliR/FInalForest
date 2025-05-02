from datetime import date

import ee
import geemap
import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

from dateutil.relativedelta import relativedelta
from tkinterweb import HtmlFrame
import threading
from datetime import datetime

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

        self.progress = None  # Will be initialized in controls

        self._setup_controls()
        self._setup_map()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Land Classification", font=("Helvetica", 16, "bold")).pack(pady=10)

        # Country selector
        ttk.Label(self.control_frame, text="Country").pack()
        self.country_var = tk.StringVar()
        self.country_dropdown = ttk.Combobox(self.control_frame, textvariable=self.country_var, state="readonly")
        self.country_dropdown['values'] = self._get_country_names()
        self.country_dropdown.set("United Kingdom")
        self.country_dropdown.pack(pady=5)

        # Time range options
        self.range_options = {
            "1 Quarter": 3,
            "Half Year": 6,
            "1 Year": 12,
            "2 Years": 24,
            "5 Years": 60
        }
        ttk.Label(self.control_frame, text="Time Range").pack()
        self.range_var = tk.StringVar()
        self.range_dropdown = ttk.Combobox(self.control_frame, textvariable=self.range_var, state="readonly")
        self.range_dropdown['values'] = list(self.range_options.keys())
        self.range_dropdown.set("1 Year")
        self.range_dropdown.pack(pady=(0, 5))

        ttk.Button(self.control_frame, text="Set Date Range", command=self._update_date_range).pack(pady=5)

        # Start/end dates
        ttk.Label(self.control_frame, text="Start Date (YYYY-MM-DD)").pack()
        self.start_date = ttk.Entry(self.control_frame)
        self.start_date.insert(0, "2023-01-01")
        self.start_date.pack()

        ttk.Label(self.control_frame, text="End Date (YYYY-MM-DD)").pack()
        self.end_date = ttk.Entry(self.control_frame)
        self.end_date.insert(0, "2023-12-31")
        self.end_date.pack()

        # Buttons
        ttk.Button(self.control_frame, text="Run Classification", command=self.run_classification).pack(pady=10)

        self.progress = ttk.Progressbar(self.control_frame, orient="horizontal", length=250, mode="determinate")
        self.progress.pack(pady=(5, 15))
        self.progress['value'] = 0

    def _get_country_names(self):
        try:
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            names = countries.aggregate_array("country_na").getInfo()
            return list(set(names))  # unique names
        except Exception as e:
            self.log(f"Failed to load country list: {e}")
            return ["United Kingdom"]  # fallback

    def _update_date_range(self):
        selected = self.range_var.get()
        months = self.range_options.get(selected, 12)
        end = date.today()
        start = end - relativedelta(months=months)
        self.start_date.delete(0, tk.END)
        self.start_date.insert(0, start.strftime("%Y-%m-%d"))
        self.end_date.delete(0, tk.END)
        self.end_date.insert(0, end.strftime("%Y-%m-%d"))
        self.log(f"Date range set: {start} to {end}")

    def _setup_map(self):
        self.html_view = HtmlFrame(self.display_frame)
        self.html_view.pack(fill='both', expand=True)

    def run_classification(self):
        threading.Thread(target=self._run_task, daemon=True).start()

    def _run_task(self):
        try:
            self.progress['value'] = 0
            self.log("Starting classification...")
            country = self.country_var.get()
            start_date = self.start_date.get()
            end_date = self.end_date.get()

            self.log(f"Filtering region: {country}")
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country))
            if self.map.layers:
                self.map.layers = [self.map.layers[0]]
            self.map.addLayer(roi, {}, "Border")
            self.progress['value'] = 20

            self.log(f"Filtering image collection for {start_date} to {end_date}")
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")

            if start_dt.year < 2013:
                landsat_collection = 'LANDSAT/LE07/C02/T1_L2'  # Landsat 7
            elif start_dt.year < 2021:
                landsat_collection = 'LANDSAT/LC08/C02/T1_L2'  # Landsat 8
            else:
                landsat_collection = 'LANDSAT/LC09/C02/T1_L2'  # Landsat 9

            self.log(f"Using dataset: {landsat_collection}")

            image = ee.ImageCollection(landsat_collection) \
                .filterDate(start_date, end_date) \
                .filterBounds(roi)

            if image.size().getInfo() == 0:
                raise Exception("No imagery found for the selected date range and region.")

            image = image.median()

            vis = {'bands': ['SR_B4', 'SR_B3', 'SR_B2'], 'min': 0, 'max': 0.3}
            self.map.addLayer(image, vis, 'Landsat RGB')
            self.map.centerObject(roi, 6)
            self.progress['value'] = 50

            self.log("Loading land cover dataset...")
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
            self.progress['value'] = 80

            self.log("Rendering map...")
            self.map.save(self.temp_html)
            self.html_view.load_html(self.temp_html)
            self.progress['value'] = 100
            self.log("Classification complete.")

        except Exception as e:
            self.progress['value'] = 0
            messagebox.showerror("Classification Error", str(e))
            self.log(f"[ERROR] {e}")