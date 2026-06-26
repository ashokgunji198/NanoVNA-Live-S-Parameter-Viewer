import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import serial # Added for physical port connection

class NanoVNAViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("NanoVNA Live S-Parameter Viewer")
        self.root.geometry("950x650")
        
        # --- UI Frame (Top) ---
        ui_frame = ttk.Frame(root)
        ui_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(ui_frame, text="COM Port:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar(value="COM3") # Default Windows port. Use /dev/ttyACM0 for Linux/Mac
        ttk.Entry(ui_frame, textvariable=self.port_var, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(ui_frame, text="Start (MHz):").grid(row=0, column=2, padx=5)
        self.start_freq_var = tk.StringVar(value="100")
        ttk.Entry(ui_frame, textvariable=self.start_freq_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(ui_frame, text="End (MHz):").grid(row=0, column=4, padx=5)
        self.end_freq_var = tk.StringVar(value="900")
        ttk.Entry(ui_frame, textvariable=self.end_freq_var, width=10).grid(row=0, column=5, padx=5)
        
        ttk.Button(ui_frame, text="Sweep & Fetch Live", command=self.plot_data).grid(row=0, column=6, padx=20)
        
        # --- Plot Frame (Bottom) ---
        self.plot_frame = ttk.Frame(root)
        self.plot_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        
        self.figure, self.ax = plt.subplots(figsize=(8, 5))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()

    def send_command(self, ser, cmd):
        """Sends a command to NanoVNA and reads the response."""
        ser.write((cmd + '\r').encode())
        lines = []
        while True:
            line = ser.readline().decode().strip()
            if line == 'ch>': # NanoVNA command prompt indicates end of data
                break
            if line and line != cmd: # Ignore the echoed command
                lines.append(line)
        return lines

    def fetch_live_data(self, port, start_f_mhz, end_f_mhz):
        """Connects to NanoVNA, sets sweep, and pulls S11/S21 data."""
        # Convert MHz to Hz for the NanoVNA command
        start_hz = int(start_f_mhz * 1e6)
        end_hz = int(end_f_mhz * 1e6)
        
        try:
            # Open serial port (NanoVNA ignores baud rate, but 115200 is standard)
            with serial.Serial(port, 115200, timeout=2) as ser:
                
                # 1. Set sweep range
                self.send_command(ser, f'sweep {start_hz} {end_hz}')
                
                # 2. Get frequencies
                freq_data = self.send_command(ser, 'frequencies')
                freqs = np.array([float(f) for f in freq_data]) / 1e6 # Convert back to MHz for plotting
                
                # 3. Get S11 (Port 0)
                s11_raw = self.send_command(ser, 'data 0')
                s11_db = []
                for line in s11_raw:
                    real, imag = map(float, line.split())
                    magnitude = np.sqrt(real**2 + imag**2)
                    s11_db.append(20 * np.log10(max(magnitude, 1e-10))) # Avoid log(0)
                
                # 4. Get S21 (Port 1)
                s21_raw = self.send_command(ser, 'data 1')
                s21_db = []
                for line in s21_raw:
                    real, imag = map(float, line.split())
                    magnitude = np.sqrt(real**2 + imag**2)
                    s21_db.append(20 * np.log10(max(magnitude, 1e-10)))
                    
                return freqs, np.array(s11_db), np.array(s21_db)
                
        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Could not connect to {port}.\n\nEnsure the NanoVNA is plugged in, powered on, and the port is not being used by another program (like NanoVNA-Saver).\n\nDetails: {e}")
            return None, None, None

    def plot_data(self):
        """Fetches live data and updates the HFSS-style plot."""
        try:
            start_f = float(self.start_freq_var.get())
            end_f = float(self.end_freq_var.get())
            port = self.port_var.get()
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numeric frequencies.")
            return
            
        # Fetch LIVE data
        freqs, s11_db, s21_db = self.fetch_live_data(port, start_f, end_f)
        
        if freqs is None:
            return # Connection failed, exit plot update
            
        # Clear and update plot
        self.ax.clear()
        
        self.ax.plot(freqs, s11_db, label="dB(S(1,1))", color='#cc0000', linewidth=2)
        self.ax.plot(freqs, s21_db, label="dB(S(2,1))", color='#0000cc', linewidth=2)
        
        self.ax.set_title("NanoVNA Live S-Parameters", fontsize=11, fontweight='bold', pad=10)
        self.ax.set_xlabel("Freq [MHz]", fontsize=10, fontweight='bold')
        self.ax.set_ylabel("dB", fontsize=10, fontweight='bold')
        
        self.ax.grid(True, which='major', linestyle='-', linewidth=0.7, color='#d3d3d3')
        self.ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='#e0e0e0')
        self.ax.minorticks_on()
        
        self.ax.legend(loc='lower right', frameon=True, edgecolor='black', fancybox=False)
        self.ax.set_xlim(start_f, end_f)
        
        self.figure.patch.set_facecolor('white')
        self.ax.set_facecolor('white')
        
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = NanoVNAViewer(root)
    root.mainloop()