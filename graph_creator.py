import os
import matplotlib.pyplot as plt
from tkinter import ttk, filedialog
import pandas as pd
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from area_count_graph import process_folder, generate_graph
import threading

class GraphCreator:
    def __init__(self, control_frame, display_frame, log_callback=None, progress_bar=None):
        self.control_frame = control_frame
        self.display_frame = display_frame
        self.log = log_callback if log_callback else print
        self.progress_bar = progress_bar
        self.folder_label = None
        self.folder = "./classified_exports"
        self._setup_controls()
        self.current_fig = None
        self.classifier = None

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Graph Creator", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        ttk.Button(self.control_frame, text="Choose Folder", command=self._choose_folder).pack(pady=3)
        self.folder_label = ttk.Label(self.control_frame, text=f"Folder: {os.path.basename(self.folder)}", wraplength=280)
        self.folder_label.pack(pady=2)
        ttk.Button(self.control_frame, text="EE Forest Chart", command=self.load_ee_graph).pack(pady=5)
        ttk.Button(self.control_frame, text="Load Area Graph (Local)", command=self.load_graph).pack(pady=5)
        ttk.Button(self.control_frame, text="Export Graph", command=self.export_graph).pack(pady=5)

    def load_ee_graph(self):
        threading.Thread(target=self._load_ee_graph_thread, daemon=True).start()

    def _load_ee_graph_thread(self):
        try:
            self._set_progress(0)
            self.log("Computing EE-based forest time series...")

            from earth_engine_graph import compute_forest_area_time_series
            if not hasattr(self, "classifier") or not self.classifier:
                raise RuntimeError("Classifier module not attached to graph viewer")

            start = int(self.classifier.start_year_var.get())
            end = int(self.classifier.end_year_var.get())
            use_custom = self.classifier.use_custom_classifier.get()
            country = self.classifier.country_var.get()

            self.log(f"Running from {start} to {end}, custom: {use_custom}")

            df = compute_forest_area_time_series(
                country,
                list(range(start, end + 1)),
                use_custom,
                log_fn=self.log,
                progress_fn=self._set_progress
            )
            self._set_progress(50)

            fig = self._generate_plot(df)
            self.current_fig = fig

            for widget in self.display_frame.winfo_children():
                widget.destroy()
            canvas = FigureCanvasTkAgg(fig, master=self.display_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            self._set_progress(100)
            self.log("EE forest graph loaded.")

        except Exception as e:
            import traceback
            self._set_progress(0)
            tb = traceback.format_exc()
            self.log(f"[EE Graph Error] {e}\n{tb}")

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder = folder
            if self.folder_label:
                self.folder_label.config(text=f"Folder: {os.path.basename(folder)}")
            self.log(f"Selected folder: {folder}")

    def _set_progress(self, value):
        if self.progress_bar:
            def update():
                self.progress_bar['value'] = value
                self.progress_bar.update_idletasks()
            self.progress_bar.after(0, update)

    def load_graph(self):
        threading.Thread(target=self._load_graph_thread, daemon=True).start()


    def _load_graph_thread(self):
        try:
            self._set_progress(0)
            self.log(f"Loading and processing images from: {self.folder}")
            df = process_folder(self.folder, progress_callback=self._set_progress)
            self._set_progress(50)
            self.log("Generating graph...")

            fig = generate_graph(df)
            self.current_fig = fig

            for widget in self.display_frame.winfo_children():
                widget.destroy()

            canvas = FigureCanvasTkAgg(fig, master=self.display_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            self._set_progress(100)
            self.log("Graph loaded successfully.")

        except Exception as e:
            self._set_progress(0)
            self.log(f"[GraphCreator] Error: {e}")

    def _generate_plot(self, df):
        df['Year'] = df['Date'].dt.year

        cols_to_plot = [
            col for col in df.columns
            if col not in ['Date', 'Month', 'Year'] and pd.api.types.is_numeric_dtype(df[col])
        ]

        group = df.groupby('Year')[cols_to_plot].sum()

        fig, ax = plt.subplots(figsize=(12, 6))
        self.log(f"EE Graph Data:\n{df}")
        group.plot(ax=ax, marker='o')

        ax.set_xlabel("Year")
        ax.set_ylabel("Area (sq km)")
        ax.set_title("Land Cover Area Over Time")
        ax.grid(True)
        plt.tight_layout()

        return fig

    def export_graph(self):
        if self.current_fig is None:
            self.log("[GraphCreator] No graph to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Save Graph As"
        )
        if file_path:
            try:
                self.current_fig.savefig(file_path)
                self.log(f"[GraphCreator] Graph saved to: {file_path}")
            except Exception as e:
                self.log(f"[GraphCreator] Failed to save graph: {e}")
