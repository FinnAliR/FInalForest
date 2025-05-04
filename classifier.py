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
    def __init__(self, control_frame, display_frame, log_callback=None, progress_callback=None):
        self.control_frame = control_frame
        self.display_frame = display_frame
        self.log = log_callback if log_callback else print
        self.set_progress = progress_callback or (lambda x: None)
        self.map = geemap.Map()
        self.temp_html = tempfile.mktemp(suffix=".html")

        self._setup_controls()
        self._setup_map()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Land Classification", font=("Helvetica", 16, "bold")).pack(pady=10)

        # Country dropdown
        ttk.Label(self.control_frame, text="Country").pack()
        self.country_var = tk.StringVar()
        self.country_dropdown = ttk.Combobox(self.control_frame, textvariable=self.country_var, state="readonly")
        self.country_dropdown['values'] = self._get_country_names()
        self.country_dropdown.set("United Kingdom")
        self.country_dropdown.pack(pady=5)

        # Start and End Year dropdowns
        ttk.Label(self.control_frame, text="Start Year").pack()
        self.start_year_var = tk.StringVar()
        self.start_year_dropdown = ttk.Combobox(self.control_frame, textvariable=self.start_year_var, state="readonly")
        self.start_year_dropdown.pack()

        ttk.Label(self.control_frame, text="End Year").pack()
        self.end_year_var = tk.StringVar()
        self.end_year_dropdown = ttk.Combobox(self.control_frame, textvariable=self.end_year_var, state="readonly")
        self.end_year_dropdown.pack()

        # Populate year ranges based on dataset availability
        self.valid_years = list(range(2017, 2024))  # ESRI dataset: 2017 to 2023
        self.start_year_dropdown['values'] = self.valid_years[:-2]  # At least 2 years range
        self.start_year_var.set(str(self.valid_years[-3]))
        self._update_end_years()

        self.start_year_dropdown.bind("<<ComboboxSelected>>", lambda e: self._update_end_years())

        # Classification button
        ttk.Button(self.control_frame, text="Run Classification", command=self.run_classification).pack(pady=10)

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

    def _update_end_years(self):
        start = int(self.start_year_var.get())
        allowed_ends = [y for y in self.valid_years if y > start]
        self.end_year_dropdown['values'] = allowed_ends
        if allowed_ends:
            self.end_year_var.set(str(allowed_ends[-1]))

    def _setup_map(self):
        self.html_view = HtmlFrame(self.display_frame)
        self.html_view.pack(fill='both', expand=True)

    def run_classification(self):
        threading.Thread(target=self._run_task, daemon=True).start()

    def _set_progress(self, value):
        if self.progress_bar:
            def update():
                self.set_progress(value)
            self.progress_bar.after(0, update)

    def _run_task(self):
        try:
            self.log("Starting yearly classification...")

            country = self.country_var.get()
            start_year = int(self.start_year_var.get())
            end_year = int(self.end_year_var.get())

            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country))
            self.map.layers = [self.map.layers[0]]
            self.map.addLayer(roi, {}, "Border")

            # Pick appropriate dataset per year
            def select_landsat_collection(year):
                if year < 2013:
                    return 'LANDSAT/LE07/C02/T1_L2'
                elif year < 2021:
                    return 'LANDSAT/LC08/C02/T1_L2'
                else:
                    return 'LANDSAT/LC09/C02/T1_L2'

            for idx, year in enumerate(range(start_year, end_year + 1)):
                self.log(f"Processing {year}...")
                progress_value = ((idx + 1) / (end_year - start_year + 1)) * 100
                self.set_progress(progress_value)

                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31"
                dataset = select_landsat_collection(year)

                collection = ee.ImageCollection(dataset) \
                    .filterDate(start_date, end_date) \
                    .filterBounds(roi)

                if collection.size().getInfo() == 0:
                    self.log(f"[Skipped] No imagery for {year}")
                    continue

                image = collection.median()
                vis = {'bands': ['SR_B4', 'SR_B3', 'SR_B2'], 'min': 0, 'max': 0.3}
                self.map.addLayer(image, vis, f'Landsat RGB {year}')

                # Optional: Add land cover layer if available
                lc_collection = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
                    .filterDate(start_date, end_date)

                if lc_collection.size().getInfo() > 0:
                    lc = lc_collection.mosaic().remap(
                        [1, 2, 3, 5, 7, 8, 9, 10, 11],
                        [1, 2, 3, 4, 5, 6, 7, 8, 9]
                    ).rename('lc')
                    self.map.addLayer(lc.clip(roi.geometry()), {
                        'min': 1, 'max': 9, 'palette': [
                            "#1A5BAB", "#358221", "#87D19E", "#FFDB5C",
                            "#ED022A", "#EDE9E4", "#F2FAFF", "#C8C8C8", "#C6AD9D"
                        ]
                    }, f"Land Cover {year}")

                progress_value = ((idx + 1) / (end_year - start_year + 1)) * 100
                self.set_progress(progress_value)

            self.map.centerObject(roi, 6)
            self.map.save(self.temp_html)
            self.html_view.load_html(self.temp_html)
            self.log("Yearly classification complete.")

        except Exception as e:
            self.set_progress(0)
            messagebox.showerror("Classification Error", str(e))
            self.log(f"[ERROR] {e}")