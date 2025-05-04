import matplotlib.pyplot as plt
from tkinter import ttk, filedialog
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from area_count_graph import process_folder, plot_area, generate_graph
import threading

class GraphCreator:
    def __init__(self, control_frame, display_frame, log_callback=None, progress_bar=None):
        self.control_frame = control_frame
        self.display_frame = display_frame
        self.log = log_callback if log_callback else print
        self.progress_bar = progress_bar
        self.folder = "classified_maps"
        self._setup_controls()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Graph Creator", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        ttk.Button(self.control_frame, text="Choose Folder", command=self._choose_folder).pack(pady=3)
        self.forest_only = tk.BooleanVar()
        ttk.Checkbutton(self.control_frame, text="Show Forest Only", variable=self.forest_only).pack(pady=5)
        ttk.Button(self.control_frame, text="Load Area Graph", command=self.load_graph).pack(pady=5)

    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder = folder
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
            df = process_folder(self.folder)
            self._set_progress(50)
            self.log("Generating graph...")

            fig = generate_graph(df, forest_only=self.forest_only.get())

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
        df['Year'] = df['Date'].dt.to_period('Y')
        group = df.groupby('Year').agg({col: 'sum' for col in df.columns if col not in ['Date', 'Month']})

        fig, ax = plt.subplots(figsize=(12, 6))
        group.plot(kind='bar', stacked=True, ax=ax)
        ax.set_ylabel("Area (sq km)")
        ax.set_title("Land Cover Area Over Time (Yearly)")
        ax.grid(axis='y')
        plt.tight_layout()
        return fig
