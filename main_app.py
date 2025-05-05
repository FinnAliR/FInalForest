import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox
from dateutil.relativedelta import relativedelta
from classifier import ClassificationApp
from graph_creator import GraphCreator
from ndvi_test import run_ndvi_analysis
from exporter import export_local_yearly_landcover, export_yearly_landcover
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
        self.root.title("LCCT: Land Cover Classification Tool")
        self.root.geometry("1300x1000")
        # Initialize Earth Engine
        try:
            ee.Initialize(project='final-project-jpp317487')
        except Exception:
            ee.Authenticate()
            ee.Initialize(project='final-project-jpp317487')
        self.auto_refresh_var = tk.BooleanVar(value=False)

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
        ttk.Button(self.left_panel, text="Independent NDVI Check", command=self.run_ndvi_analysis).pack(pady=(10, 5))

        self.cancel_event = threading.Event()
        self._setup_batch_export_controls()

        self.tile_size_deg = 0.4
        self.default_scale = 10

        self.graph_viewer = GraphCreator(self.left_panel, self.right_panel, self.log_status, self.progress_bar)
        self.graph_viewer.classifier = self.classifier

    def choose_export_folder(self):
        folder = tk.filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.folder_label.config(text=f"Folder: {os.path.basename(folder)}")
            self.log_status(f"Export folder set to: {folder}")

    def _setup_batch_export_controls(self):
        ttk.Label(self.left_panel, text="\nBatch Export", font=("Helvetica", 14, "bold")).pack(pady=10)

        notebook = ttk.Notebook(self.left_panel)
        notebook.pack(fill='both', expand=False, pady=5)

        # --- Tab 1: Google Drive ---
        self.tab_drive = ttk.Frame(notebook)
        notebook.add(self.tab_drive, text="Export to Drive")
        ttk.Button(self.tab_drive, text="Export Images to Drive", command=self.run_batch_export).pack(pady=5)

        # --- Tab 2: Local Export ---
        self.tab_local = ttk.Frame(notebook)
        notebook.add(self.tab_local, text="Export to Local")
        self.output_folder = "./classified_exports"
        ttk.Button(self.tab_local, text="Choose Export Folder", command=self.choose_export_folder).pack(pady=5)

        self.folder_label = ttk.Label(self.tab_local, text=f"Folder: {os.path.basename(self.output_folder)}", wraplength=280)
        self.folder_label.pack(pady=2)
        ttk.Button(self.tab_local, text="Set Export Options", command=self._show_export_options).pack(pady=5)
        ttk.Button(self.tab_local, text="Export Locally", command=self.run_local_export).pack(pady=5)
        ttk.Button(self.tab_local, text="Cancel Export", command=self.cancel_export).pack(side=tk.LEFT, padx=5)

    def _show_export_options(self):
        win = tk.Toplevel(self.root)
        win.title("Export Options")
        win.geometry("300x180")

        ttk.Checkbutton(self.tab_drive, text="Auto-refresh graph when done", variable=self.auto_refresh_var).pack(pady=5)

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

    def cancel_export(self):
        self.cancel_event.set()
        self.log_status("Local export canceled by user.")

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
        self.status_text.after(0, lambda: self.status_text.delete("1.0", tk.END))
        country = self.classifier.country_var.get()
        self.status_text.after(0, lambda: self.log_status("Starting export to Drive..."))
        start = f"{self.classifier.start_year_var.get()}-01-01"
        end = f"{self.classifier.end_year_var.get()}-12-31"

        try:
            tasks = export_yearly_landcover(country, start, end)
            # Schedule the following logs on the GUI thread:
            self.status_text.after(0, lambda: self.log_status(f"\nStarted {len(tasks)} tasks:"))
            for year, i, j, task in tasks:
                msg = f"{year} tile ({i},{j}): {getattr(task, 'id', task)}"
                self.status_text.after(0, lambda m=msg: self.log_status(m))
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
        self.cancel_event.clear()
        start = f"{self.classifier.start_year_var.get()}-01-01"
        end = f"{self.classifier.end_year_var.get()}-12-31"
        threading.Thread(
            target=lambda: export_local_yearly_landcover(
                country_name=self.classifier.country_var.get(),
                start_date_str=start,
                end_date_str=end,
                output_folder=self.output_folder,
                tile_size_deg=self.tile_size_deg,
                scale=self.default_scale,
                use_custom=self.classifier.use_custom_classifier.get(),  # <-- here
                log_fn=self.log_status,
                progress_fn=lambda v: self.progress_bar.config(value=v),
                cancel_event=self.cancel_event
            ), daemon=True
        ).start()

    def run_ndvi_analysis(self):
        # gather parameters
        country = self.classifier.country_var.get()
        start = int(self.classifier.start_year_var.get())
        end = int(self.classifier.end_year_var.get())
        # clear status
        self.status_text.after(0, lambda: self.status_text.delete("1.0", tk.END))
        # start analysis in thread
        threading.Thread(
            target=lambda: run_ndvi_analysis(
                country_name=country,
                start_year=start,
                end_year=end,
                log_fn=self.log_status,
                progress_fn=lambda v: self.progress_bar.config(value=v),
                display_frame=self.right_panel
            ),
            daemon=True
        ).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = LandApp(root)
    root.mainloop()
