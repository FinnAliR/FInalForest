import os
import pandas as pd
import matplotlib.pyplot as plt
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from area_count_graph import process_folder, plot_area

class GraphViewer:
    def __init__(self, control_frame, display_frame):
        self.control_frame = control_frame
        self.display_frame = display_frame
        self._setup_controls()

    def _setup_controls(self):
        ttk.Label(self.control_frame, text="Graph Viewer", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        ttk.Button(self.control_frame, text="Load Area Graph", command=self.load_graph).pack(pady=5)

    def load_graph(self):
        try:
            df = process_folder("classified_maps")
            fig = self._generate_plot(df)

            for widget in self.display_frame.winfo_children():
                widget.destroy()

            canvas = FigureCanvasTkAgg(fig, master=self.display_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            print(f"[GraphViewer] Error: {e}")

    def _generate_plot(self, df):
        df['Month'] = df['Date'].dt.to_period('M')
        group = df.groupby('Month').sum()
        group.drop(columns=['Date'], errors='ignore', inplace=True)

        fig, ax = plt.subplots(figsize=(12, 6))
        group.plot(kind='bar', stacked=True, ax=ax)
        ax.set_ylabel("Area (sq km)")
        ax.set_title("Land Cover Area Over Time (Monthly)")
        ax.grid(axis='y')
        plt.tight_layout()
        return fig