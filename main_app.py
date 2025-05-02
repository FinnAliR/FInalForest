import tkinter as tk
from datetime import date
from tkinter import ttk, messagebox

from dateutil.relativedelta import relativedelta

from classifier import ClassificationApp
from graph_viewer import GraphViewer
from exporter import export_monthly_landcover
import threading
import ee
import time
import os

class LandApp:
    def log_status(self, message):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)

    def __init__(self, root):
        self.root = root
        self.root.title("Land Cover Classification")
        self.root.geometry("1300x900")

        # Layout frames
        self.left_panel = ttk.Frame(root, width=320, padding=10)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)

        self.right_panel = ttk.Frame(root)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Status box
        self.status_text = tk.Text(self.left_panel, height=8, width=40)
        self.status_text.pack(pady=5)

        # Modules
        self.classifier = ClassificationApp(self.left_panel, self.right_panel, self.log_status)
        self.graph_viewer = GraphViewer(self.left_panel, self.right_panel, self.log_status)

        self._setup_batch_export_controls()

    def _setup_batch_export_controls(self):
        ttk.Label(self.left_panel, text="\nBatch Export", font=("Helvetica", 14, "bold")).pack(pady=10)

        notebook = ttk.Notebook(self.left_panel)
        notebook.pack(fill='both', expand=False, pady=5)

        # --- Tab 1: Google Drive ---
        self.tab_drive = ttk.Frame(notebook)
        notebook.add(self.tab_drive, text="Export to Drive")

        self.auto_refresh_var = tk.BooleanVar()
        ttk.Checkbutton(self.tab_drive, text="Auto-refresh graph when done", variable=self.auto_refresh_var).pack(
            pady=5)
        ttk.Button(self.tab_drive, text="Export Monthly Images to Drive", command=self.run_batch_export).pack(pady=5)

        # --- Tab 2: Local Export ---
        self.tab_local = ttk.Frame(notebook)
        notebook.add(self.tab_local, text="Export to Local")

        ttk.Label(self.tab_local, text="Output Folder").pack()
        self.output_folder_entry = ttk.Entry(self.tab_local, width=30)
        self.output_folder_entry.insert(0, "./classified_exports")
        self.output_folder_entry.pack(pady=5)

        ttk.Label(self.tab_local, text="Resolution (meters)").pack()
        self.local_scale_entry = ttk.Entry(self.tab_local, width=10)
        self.local_scale_entry.insert(0, "10")
        self.local_scale_entry.pack(pady=5)

        ttk.Button(self.tab_local, text="Export Locally", command=self.run_local_export).pack(pady=5)

    def load_country_list(self):
        try:
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            names = countries.aggregate_array("country_na").getInfo()
            unique_names = sorted(set(names))
            self.country_dropdown['values'] = unique_names
        except Exception as e:
            self.log_status(f"[ERROR] Could not load country list: {e}")
            self.country_dropdown['values'] = ["United Kingdom"]

    def _update_date_range(self):
        selected = self.range_var.get()
        months = self.range_options.get(selected, 12)
        end_date = date.today()
        start_date = end_date - relativedelta(months=months)

        self.start_entry.delete(0, tk.END)
        self.start_entry.insert(0, start_date.strftime("%Y-%m-%d"))

        self.end_entry.delete(0, tk.END)
        self.end_entry.insert(0, end_date.strftime("%Y-%m-%d"))

        self.log_status(f"Date range set: {start_date} to {end_date}")

    def run_batch_export(self):
        threading.Thread(target=self._batch_export_thread, daemon=True).start()

    def _batch_export_thread(self):
        self.status_text.delete("1.0", tk.END)
        country = self.classifier.country_var.get()
        start = self.classifier.start_date.get()
        end = self.classifier.end_date.get()

        try:
            tasks = export_monthly_landcover(country, start, end, project_id='final-project-jpp317487')
            self.log_status(f"\nStarted {len(tasks)} tasks:")
            for month, task_id in tasks:
                self.log_status(f"{month}: {task_id}")
            messagebox.showinfo("Batch Export", "Monthly export tasks started. This may take a few minutes.\nLive status will update below.")

            # Live status polling
            while True:
                active_tasks = [t for t in ee.batch.Task.list() if t.status()['state'] in ['READY', 'RUNNING']]
                status_summary = "\nTask Status:\n"
                for t in ee.batch.Task.list():
                    status = t.status()
                    description = status.get('description', 'No description')
                    state = status.get('state', 'UNKNOWN')
                    error = status.get('error_message', '')
                    status_summary += f"{description}: {state}"
                    if error:
                        status_summary += f" [Error: {error}]"
                    status_summary += "\n"

                self.log_status(status_summary)
                if not active_tasks:
                    self.log_status("\nAll tasks completed.")
                    break
                time.sleep(10)

            if self.auto_refresh_var.get():
                self.graph_viewer.load_graph()

        except Exception as e:
            messagebox.showerror("Export Failed", str(e))
            self.log_status(f"Error: {str(e)}")

    def run_local_export(self):
        threading.Thread(target=self._local_export_thread, daemon=True).start()

    def _local_export_thread(self):
        self.status_text.delete("1.0", tk.END)
        country = self.classifier.country_var.get()
        start_date = self.classifier.start_date.get()
        end_date = self.classifier.end_date.get()
        scale = int(self.local_scale_entry.get())
        output_folder = self.output_folder_entry.get()

        os.makedirs(output_folder, exist_ok=True)

        self.log_status(f"Starting local export to: {output_folder}")
        self.log_status(f"Country: {country}, Range: {start_date} to {end_date}, Scale: {scale}m")

        try:
            ee.Initialize(project='final-project-jpp317487')
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country))

            from datetime import datetime, timedelta
            current = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            while current <= end:
                next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
                label = current.strftime("%Y-%m")

                collection = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
                    .filterDate(current.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d"))

                if collection.size().getInfo() == 0:
                    self.log_status(f"[Skipped] No data for {label}")
                else:
                    image = collection.mosaic().remap(
                        [1, 2, 3, 5, 7, 8, 9, 10, 11],
                        [1, 2, 3, 4, 5, 6, 7, 8, 9]
                    ).rename('lc')

                    path = os.path.join(output_folder, f"land_cover_{country.replace(' ', '_')}_{label}.tif")
                    url = image.clip(roi.geometry()).getDownloadURL({
                        'region': roi.geometry(),
                        'scale': scale,
                        'format': 'GeoTIFF'
                    })

                    # Download the file
                    import urllib.request
                    self.log_status(f"Downloading {label}...")
                    urllib.request.urlretrieve(url, path)
                    self.log_status(f"Saved: {path}")

                current = next_month

            self.log_status("Local export complete.")

        except Exception as e:
            self.log_status(f"[ERROR] {e}")
            messagebox.showerror("Local Export Failed", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = LandApp(root)
    root.mainloop()
