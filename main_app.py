import tkinter as tk
import urllib
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.error
import random
from classifier import ClassificationApp
from graph_creator import GraphCreator
from exporter import export_yearly_landcover
import threading
import ee
import time
import os

class LandApp:
    def log_status(self, message):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)

    def export_logs_to_txt(self):
        log_content = self.status_text.get("1.0", tk.END)
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = os.path.join("logs", f"log_{timestamp}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        self.log_status(f"Logs exported to {file_path}")

    def __init__(self, root):
        self.root = root
        self.root.title("Land Cover Classification")
        self.root.geometry("1300x900")

        # Top container for main UI
        self.top_container = ttk.Frame(root)
        self.top_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.left_panel = ttk.Frame(self.top_container, width=320, padding=10)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)

        self.right_panel = ttk.Frame(self.top_container)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Bottom container for logs and progress
        self.bottom_container = ttk.Frame(root)
        self.bottom_container.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_frame = ttk.Frame(self.bottom_container)
        self.status_frame.pack(side=tk.TOP, fill=tk.X, expand=False)

        self.status_text = tk.Text(self.status_frame, height=8)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=5)

        self.export_button = ttk.Button(self.status_frame, text="Export Logs to TXT", command=self.export_logs_to_txt)
        self.export_button.pack(side=tk.RIGHT, padx=(5, 10), pady=5)

        self.progress_bar = ttk.Progressbar(self.bottom_container, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 5))

        # Modules
        self.classifier = ClassificationApp(
            self.left_panel,
            self.right_panel,
            log_callback=self.log_status,
            progress_callback=lambda v: self.progress_bar.config(value=v)
        )
        self.graph_viewer = GraphCreator(self.left_panel, self.right_panel, self.log_status, self.progress_bar)

        self._setup_batch_export_controls()

        self.tile_size_deg = 0.2
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
        ttk.Button(self.tab_local, text="Set Export Options", command=self._show_export_options).pack(pady=5)
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
                   command=lambda: [tile_entry.delete(0, tk.END), tile_entry.insert(0, "0.2"),
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
        start = f"{self.classifier.start_year_var.get()}-01-01"
        end = f"{self.classifier.end_year_var.get()}-12-31"

        threading.Thread(target=self._batch_export_thread, daemon=True).start()

    def _batch_export_thread(self):
        self.status_text.delete("1.0", tk.END)
        country = self.classifier.country_var.get()
        start = f"{self.classifier.start_year_var.get()}-01-01"
        end = f"{self.classifier.end_year_var.get()}-12-31"

        try:
            tasks = export_yearly_landcover(country, start, end, project_id='final-project-jpp317487')
            self.log_status(f"\nStarted {len(tasks)} tasks:")
            for month, task_id in tasks:
                self.log_status(f"{month}: {task_id}")
            messagebox.showinfo("Batch Export", "export tasks started. This may take a few minutes.\nLive status will update below.")
            self.progress_bar['value'] = 0
            self.progress_bar.update_idletasks()
            # Live status polling
            total_tasks = len(tasks)
            completed = 0

            while True:
                active_tasks = []
                completed = 0
                for t in ee.batch.Task.list():
                    status = t.status()
                    if status['state'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        completed += 1
                    else:
                        active_tasks.append(t)

                self.progress_bar['value'] = (completed / total_tasks) * 100
                self.progress_bar.update_idletasks()

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
                    break
                time.sleep(10)

            if self.auto_refresh_var.get():
                self.graph_viewer.load_graph()

            self.progress_bar['value'] = 100
            self.progress_bar.update_idletasks()

        except Exception as e:
            messagebox.showerror("Export Failed", str(e))
            self.log_status(f"Error: {str(e)}")

    def run_local_export(self):
        start = f"{self.classifier.start_year_var.get()}-01-01"
        end = f"{self.classifier.end_year_var.get()}-12-31"
        threading.Thread(target=self._local_export_thread, daemon=True).start()

    def _local_export_thread(self):
        self.status_text.delete("1.0", tk.END)
        country = self.classifier.country_var.get()
        start_date = self.classifier.start_date.get()
        end_date = self.classifier.end_date.get()
        output_folder = self.output_folder_entry.get()
        tile_deg = self.tile_size_deg
        scale = self.default_scale
        self.progress_bar['value'] = 0
        self.progress_bar.update_idletasks()
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

            total_tiles = x_tiles * y_tiles
            total_months = 0

            tmp = datetime.strptime(start_date, "%Y-%m-%d")
            while tmp <= end:
                total_months += 1
                tmp = (tmp.replace(day=28) + timedelta(days=4)).replace(day=1)

            total_downloads = total_tiles * total_months
            current_download = 0

            while current.year <= end.year:
                year_start = datetime(current.year, 1, 1)
                year_end = datetime(current.year + 1, 1, 1)
                label = f"{current.year}"

                collection = ee.ImageCollection(...).filterDate(year_start.strftime("%Y-%m-%d"), year_end.strftime("%Y-%m-%d"))

                if collection.size().getInfo() == 0:
                    self.log_status(f"[Skipped] No data for {label}")
                    current = datetime(current.year + 1, 1, 1)
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
                            # Clip image to tile
                            clipped = image.clip(tile_geom)

                            # Check that it has non-empty bands before attempting export
                            band_names = clipped.bandNames().getInfo()
                            if not band_names:
                                self.log_status(f"[Skipped] {filename}: No valid bands in this tile.")
                                continue

                            intersection = roi.intersection(tile_geom, ee.ErrorMargin(1))
                            area = intersection.area().getInfo()
                            if area < 1000:  # Less than 1000 m² = skip
                                self.log_status(f"[Skipped] {filename}: Negligible intersection with ROI.")
                                continue

                            url = clipped.getDownloadURL({
                                'region': tile_geom,
                                'scale': scale,
                                'format': 'GeoTIFF'
                            })

                            self.log_status(f"Downloading {filename}...")
                            urllib.request.urlretrieve(url, path)
                            self.log_status(f"Saved: {path}")
                        except Exception as e:
                            self.log_status(f"[Tile Failed] {filename}: {e}")

                        current_download += 1
                        self.progress_bar['value'] = (current_download / total_downloads) * 100
                        self.progress_bar.update_idletasks()
                current = datetime(current.year + 1, 1, 1)

            self.log_status("Tiled local export complete.")
            self.progress_bar['value'] = 100
            self.progress_bar.update_idletasks()
        except Exception as e:
            self.log_status(f"[ERROR] {e}")
            messagebox.showerror("Export Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = LandApp(root)
    root.mainloop()
