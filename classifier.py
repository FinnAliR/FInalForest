from datetime import date
import ee
import geemap
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from dateutil.relativedelta import relativedelta
import sys, os, tkinter as tk
import threading
import webbrowser


# Import shared classification utilities
from classification_utils import (
    select_landsat_collection,
    build_esri_image,
    build_custom_forest_image
)

class ClassificationApp:
    def __init__(self, control_frame, display_frame, log_callback=None, progress_callback=None):
        self.root = control_frame.winfo_toplevel()
        self.control_frame = control_frame
        self.display_frame = display_frame
        self.log = log_callback or print
        self.set_progress = progress_callback or (lambda x: None)
        self.map = geemap.Map()
        self.temp_html = tempfile.mktemp(suffix=".html")
        self._setup_controls()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Land Classification", font=("Helvetica", 16, "bold")).pack(pady=10)

        # Country dropdown
        ttk.Label(self.control_frame, text="Country").pack()
        self.country_var = tk.StringVar()
        self.country_dropdown = ttk.Combobox(
            self.control_frame, textvariable=self.country_var, state="readonly"
        )
        self.country_dropdown['values'] = self._get_country_names()
        self.country_dropdown.set("United Kingdom")
        self.country_dropdown.pack(pady=5)

        # Year range selectors
        ttk.Label(self.control_frame, text="Start Year").pack()
        self.start_year_var = tk.StringVar()
        self.start_year_dropdown = ttk.Combobox(
            self.control_frame, textvariable=self.start_year_var, state="readonly"
        )
        self.start_year_dropdown.pack()

        ttk.Label(self.control_frame, text="End Year").pack()
        self.end_year_var = tk.StringVar()
        self.end_year_dropdown = ttk.Combobox(
            self.control_frame, textvariable=self.end_year_var, state="readonly"
        )
        self.end_year_dropdown.pack()

        # Populate valid years
        self.valid_years = list(range(2017, 2024))
        self.start_year_dropdown['values'] = self.valid_years[:-2]
        self.start_year_var.set(str(self.valid_years[-3]))
        self._update_end_years()
        self.start_year_dropdown.bind("<<ComboboxSelected>>", lambda e: self._update_end_years())

        # Toggle for custom classifier
        self.use_custom_classifier = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.control_frame,
            text="Use Custom Forest Classifier",
            variable=self.use_custom_classifier
        ).pack(pady=5)

        # Run button
        ttk.Button(
            self.control_frame,
            text="Run Classification",
            command=self.run_classification
        ).pack(pady=10)

        ttk.Button(
            self.control_frame,
            text="Open Map in Browser",
            command=self._open_map_html
        ).pack(pady=5)

    def _get_country_names(self):
        try:
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            names = countries.aggregate_array("country_na").getInfo()
            return sorted(set(names))
        except Exception as e:
            self.log(f"Failed to load country list: {e}")
            return ["United Kingdom"]

    def _update_end_years(self):
        start = int(self.start_year_var.get())
        allowed = [y for y in self.valid_years if y > start]
        self.end_year_dropdown['values'] = allowed
        if allowed:
            self.end_year_var.set(str(allowed[-1]))

    def run_classification(self):
        threading.Thread(target=self._run_task, daemon=True).start()

    def _run_task(self):
        try:
            self.log("Starting yearly classification...")
            country = self.country_var.get()
            start_year = int(self.start_year_var.get())
            end_year = int(self.end_year_var.get())

            # Define ROI
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country)).geometry()
            total_years = end_year - start_year + 1

            for idx, year in enumerate(range(start_year, end_year + 1)):
                self.set_progress((idx / total_years) * 100)

                # Build classified image
                try:
                    if self.use_custom_classifier.get():
                        img = build_custom_forest_image(year, roi)
                        self.log(f" Custom Processing {year}...")
                    else:
                        img = build_esri_image(year, roi)
                        self.log(f"ERSI Processing {year}...")
                    # assign timestamp
                    img = img.set('system:time_start', ee.Date(f'{year}-01-01').millis())
                    layer_name = (
                        f"Forest Cover {year}" if self.use_custom_classifier.get()
                        else f"Land Cover {year}"
                        )
                    vis = {
                        'min': 1, 'max': 9,
                        'palette': [
                            "#1A5BAB", "#358221", "#87D19E", "#FFDB5C",
                            "#ED022A", "#EDE9E4", "#F2FAFF", "#C8C8C8", "#C6AD9D"
                        ]
                        }
                    self.map.addLayer(img.clip(roi), vis, layer_name)
                except Exception as e:
                    self.log(f"[Skipped] Year {year} failed: {e}")

                self.set_progress(((idx + 1) / total_years) * 100)

            # Finalize display
            self.map.centerObject(roi, 6)
            self.map.to_html(self.temp_html)
            self.log(f"Map saved to: {self.temp_html}")
            self.log("Yearly classification complete.")

        except Exception as e:
            self.set_progress(0)
            messagebox.showerror("Classification Error", str(e))
            self.log(f"[ERROR] {e}")

    def _open_map_html(self):
        try:
            if not os.path.exists(self.temp_html):
                messagebox.showwarning("Missing Map", "Please run classification first.")
                return
            webbrowser.open(f"file://{self.temp_html}")
            self.log(f"Opening map in browser: {self.temp_html}")
        except Exception as e:
            self.log(f"[Error opening map HTML] {e}")
            messagebox.showerror("Open Map Error", str(e))
