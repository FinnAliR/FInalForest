import tkinter as tk
import urllib
from datetime import date, datetime, timedelta
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

        self.tile_size_deg = 2.0
        self.default_scale = 10

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

        ttk.Button(self.tab_local, text="Set Export Options", command=self._show_export_options).pack(pady=2)
        ttk.Button(self.tab_local, text="Export Locally", command=self.run_local_export).pack(pady=5)

    def _show_export_options(self):
        win = tk.Toplevel(self.root)
        win.title("Export Options")
        win.geometry("300x180")

        ttk.Label(win, text="Tile Size (degrees):").pack(pady=5)
        tile_entry = ttk.Entry(win)
        tile_entry.insert(0, str(self.tile_size_deg))
        tile_entry.pack()

        ttk.Label(win, text="Resolution (m):").pack(pady=5)
        scale_entry = ttk.Entry(win)
        scale_entry.insert(0, str(self.default_scale))
        scale_entry.pack()

        def save_settings():
            try:
                self.tile_size_deg = float(tile_entry.get())
                self.default_scale = int(scale_entry.get())
                messagebox.showinfo("Saved", "Export settings updated.")
                win.destroy()
            except:
                messagebox.showerror("Invalid Input", "Please enter valid numbers.")

        ttk.Button(win, text="Save", command=save_settings).pack(pady=10)
        ttk.Button(win, text="Reset Defaults",
                   command=lambda: [tile_entry.delete(0, tk.END), tile_entry.insert(0, "2.0"),
                                    scale_entry.delete(0, tk.END), scale_entry.insert(0, "10")]).pack()

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
        from shapely.geometry import box

        self.status_text.delete("1.0", tk.END)
        country = self.classifier.country_var.get()
        start_date = self.classifier.start_date.get()
        end_date = self.classifier.end_date.get()
        output_folder = self.output_folder_entry.get()
        tile_deg = self.tile_size_deg
        scale = self.default_scale

        os.makedirs(output_folder, exist_ok=True)

        self.log_status(f"Starting tiled local export to: {output_folder}")
        try:
            ee.Initialize(project='final-project-jpp317487')
            countries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
            roi = countries.filter(ee.Filter.eq("country_na", country)).geometry()
            bounds = roi.bounds().coordinates().get(0).getInfo()

            lons = [pt[0] for pt in bounds]
            lats = [pt[1] for pt in bounds]
            minx, maxx = min(lons), max(lons)
            miny, maxy = min(lats), max(lats)

            x_tiles = int((maxx - minx) // tile_deg) + 1
            y_tiles = int((maxy - miny) // tile_deg) + 1

            current = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            while current <= end:
                next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
                label = current.strftime("%Y-%m")

                collection = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS') \
                    .filterDate(current.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d"))

                if collection.size().getInfo() == 0:
                    self.log_status(f"[Skipped] No data for {label}")
                    current = next_month
                    continue

                image = collection.mosaic().remap(
                    [1, 2, 3, 5, 7, 8, 9, 10, 11],
                    [1, 2, 3, 4, 5, 6, 7, 8, 9]
                ).rename('lc')

                for i in range(x_tiles):
                    for j in range(y_tiles):
                        tile_geom = ee.Geometry.Rectangle([minx + i * tile_deg, miny + j * tile_deg,
                                                           min(minx + (i + 1) * tile_deg, maxx),
                                                           min(miny + (j + 1) * tile_deg, maxy)])

                        filename = f"land_cover_{country.replace(' ', '_')}_{label}_tile_{i}_{j}.tif"
                        path = os.path.join(output_folder, filename)

                        try:
                            url = image.clip(tile_geom).getDownloadURL({
                                'region': tile_geom,
                                'scale': scale,
                                'format': 'GeoTIFF'
                            })

                            self.log_status(f"Downloading {filename}...")
                            urllib.request.urlretrieve(url, path)
                            self.log_status(f"Saved: {path}")
                        except Exception as e:
                            self.log_status(f"[Tile Failed] {filename}: {e}")

                current = next_month

            self.log_status("✅ Tiled local export complete.")
        except Exception as e:
            self.log_status(f"[ERROR] {e}")
            messagebox.showerror("Export Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = LandApp(root)
    root.mainloop()
