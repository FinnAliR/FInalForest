import tkinter as tk
from tkinter import ttk, messagebox
from classifier import ClassificationApp
from graph_viewer import GraphViewer
from exporter import export_monthly_landcover
import threading
import time
import os

# Import Earth Engine with Windows compatibility
try:
    import ee
    ee.Initialize()
except ImportError:
    print("Please install the Earth Engine API using: pip install earthengine-api")
    exit(1)
except Exception as e:
    print(f"Earth Engine initialization error: {e}")
    print("Please authenticate using: ee.Authenticate()")
    exit(1)

class LandApp:
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
        self.graph_viewer = GraphViewer(self.left_panel, self.right_panel)

        self._setup_batch_export_controls()

    def _setup_batch_export_controls(self):
        ttk.Label(self.left_panel, text="\nBatch Export", font=("Helvetica", 14, "bold")).pack(pady=10)

        self.country_entry = ttk.Entry(self.left_panel)
        self.country_entry.insert(0, "United Kingdom")
        ttk.Label(self.left_panel, text="Country").pack()
        self.country_entry.pack()

        self.start_entry = ttk.Entry(self.left_panel)
        self.start_entry.insert(0, "2023-01-01")
        ttk.Label(self.left_panel, text="Start Date (YYYY-MM-DD)").pack()
        self.start_entry.pack()

        self.end_entry = ttk.Entry(self.left_panel)
        self.end_entry.insert(0, "2023-12-31")
        ttk.Label(self.left_panel, text="End Date (YYYY-MM-DD)").pack()
        self.end_entry.pack()

        self.auto_refresh_var = tk.BooleanVar()
        ttk.Checkbutton(self.left_panel, text="Auto-refresh graph when done", variable=self.auto_refresh_var).pack(pady=5)

        ttk.Button(self.left_panel, text="Export Monthly Images to Drive", command=self.run_batch_export).pack(pady=5)

    def log_status(self, message):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)

    def run_batch_export(self):
        threading.Thread(target=self._batch_export_thread, daemon=True).start()

    def _batch_export_thread(self):
        self.status_text.delete("1.0", tk.END)
        country = self.country_entry.get()
        start = self.start_entry.get()
        end = self.end_entry.get()

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
                    status_summary += f"{status['description']}: {status['state']}\n"
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

if __name__ == "__main__":
    root = tk.Tk()
    app = LandApp(root)
    root.mainloop()
