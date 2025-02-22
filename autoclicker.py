import tkinter as tk
from tkinter import ttk
import threading
import keyboard # type: ignore
import time
from pynput.mouse import Button, Controller # type: ignore

class AutoClickerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Auto Clicker")
        self.root.geometry("320x430")  # Increased height for new widgets

        # Default hotkey values
        self.start_key = "F6"
        self.quit_key = "F5"
        self.set_clicks_key = "F7"
        self.capturing_hotkey = None  # Will be set to "start", "quit", or "set_clicks" when capturing

        self.clicking = False
        self.mouse = Controller()
        self.click_count = 0
        self.click_times = []  # For tracking click timestamps (for CPS)
        self.set_clicks_remaining = None  # When not None, we are in "set number" mode

        # Click interval control
        self.interval_frame = ttk.LabelFrame(self.root, text="Click Interval (seconds)")
        self.interval_frame.pack(padx=10, pady=5, fill="x")
        
        self.interval_value = tk.DoubleVar(value=0.005)
        self.interval_spinbox = ttk.Spinbox(
            self.interval_frame,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.interval_value
        )
        self.interval_spinbox.pack(padx=5, pady=5)
        
        # Click counter
        self.counter_label = ttk.Label(self.root, text="Clicks: 0")
        self.counter_label.pack(pady=5)
        
        # CPS display
        self.cps_label = ttk.Label(self.root, text="CPS: 0")
        self.cps_label.pack(pady=5)
        
        # Start/Stop button
        self.toggle_button = ttk.Button(
            self.root,
            text=f"Start ({self.start_key})",
            command=self.toggle_clicking
        )
        self.toggle_button.pack(pady=10)
        
        # Click Set Options
        self.set_frame = ttk.LabelFrame(self.root, text="Click Set Options")
        self.set_frame.pack(padx=10, pady=5, fill="x")
        
        ttk.Label(self.set_frame, text="Number of Clicks:").pack(padx=5, pady=2, anchor="w")
        self.set_clicks_var = tk.IntVar(value=10)
        self.set_clicks_entry = ttk.Entry(self.set_frame, textvariable=self.set_clicks_var)
        self.set_clicks_entry.pack(padx=5, pady=2, fill="x")
        
        self.set_clicks_button = ttk.Button(
            self.set_frame,
            text="Click Set",
            command=self.start_set_clicks
        )
        self.set_clicks_button.pack(pady=5)
        
        # Hotkeys display
        self.hotkey_frame = ttk.LabelFrame(self.root, text="Current Hotkeys")
        self.hotkey_frame.pack(padx=10, pady=5, fill="x")
        self.hotkey_display_var = tk.StringVar()
        self.update_hotkey_display()
        self.hotkey_display_label = ttk.Label(self.hotkey_frame, textvariable=self.hotkey_display_var)
        self.hotkey_display_label.pack(pady=5)
        
        # Hotkey settings: allow changing hotkeys by capturing the next key press.
        self.hotkey_settings_frame = ttk.LabelFrame(self.root, text="Change Hotkeys (Click a button then press a key)")
        self.hotkey_settings_frame.pack(padx=10, pady=5, fill="x")
        
        self.start_hotkey_button = ttk.Button(
            self.hotkey_settings_frame,
            text=f"Start/Stop: {self.start_key}",
            command=lambda: self.capture_hotkey_for("start")
        )
        self.start_hotkey_button.pack(padx=5, pady=2, fill="x")
        
        self.quit_hotkey_button = ttk.Button(
            self.hotkey_settings_frame,
            text=f"Quit: {self.quit_key}",
            command=lambda: self.capture_hotkey_for("quit")
        )
        self.quit_hotkey_button.pack(padx=5, pady=2, fill="x")
        
        self.set_clicks_hotkey_button = ttk.Button(
            self.hotkey_settings_frame,
            text=f"Set Clicks: {self.set_clicks_key}",
            command=lambda: self.capture_hotkey_for("set_clicks")
        )
        self.set_clicks_hotkey_button.pack(padx=5, pady=2, fill="x")
        
        # A status label to show instructions when capturing a key
        self.status_label = ttk.Label(self.root, text="")
        self.status_label.pack(pady=5)
        
        # Bind initial hotkeys using the keyboard module.
        self.bind_hotkeys()
        
        # Start background threads
        self.click_thread = threading.Thread(target=self.auto_click, daemon=True)
        self.click_thread.start()
        self.root.after(100, self.update_cps)  # Start CPS updater

    def bind_hotkeys(self):
        # Remove existing hotkey bindings if they exist.
        try:
            keyboard.remove_hotkey(self.start_hotkey_id)
        except AttributeError:
            pass
        try:
            keyboard.remove_hotkey(self.quit_hotkey_id)
        except AttributeError:
            pass
        try:
            keyboard.remove_hotkey(self.set_clicks_hotkey_id)
        except AttributeError:
            pass
        
        self.start_hotkey_id = keyboard.on_press_key(self.start_key, lambda _: self.toggle_clicking())
        self.quit_hotkey_id = keyboard.on_press_key(self.quit_key, lambda _: self.root.quit())
        self.set_clicks_hotkey_id = keyboard.on_press_key(self.set_clicks_key, lambda _: self.start_set_clicks())
        
    def update_hotkey_display(self):
        display_text = (
            f"Start/Stop: {self.start_key}\n"
            f"Quit: {self.quit_key}\n"
            f"Set Clicks: {self.set_clicks_key}"
        )
        self.hotkey_display_var.set(display_text)
        # Also update the text on the start/stop button.
        self.toggle_button.config(
            text=("Stop (" + self.start_key + ")" if self.clicking else "Start (" + self.start_key + ")")
        )
        
    def capture_hotkey_for(self, hotkey_type):
        """
        Prepare to capture the next key press to update a hotkey.
        hotkey_type should be one of: "start", "quit", "set_clicks"
        """
        self.capturing_hotkey = hotkey_type
        self.status_label.config(text=f"Press a key to set for {hotkey_type.replace('_', ' ').title()}")
        # Bind the next key press (using bind_all to ensure we catch it regardless of focus)
        self.root.bind_all("<Key>", self.on_key_capture)
        
    def on_key_capture(self, event):
        new_key = event.keysym  # Use the keysym for readability.
        if self.capturing_hotkey == "start":
            self.start_key = new_key
            self.start_hotkey_button.config(text=f"Start/Stop: {new_key}")
        elif self.capturing_hotkey == "quit":
            self.quit_key = new_key
            self.quit_hotkey_button.config(text=f"Quit: {new_key}")
        elif self.capturing_hotkey == "set_clicks":
            self.set_clicks_key = new_key
            self.set_clicks_hotkey_button.config(text=f"Set Clicks: {new_key}")
        
        self.bind_hotkeys()
        self.update_hotkey_display()
        self.status_label.config(text=f"Updated {self.capturing_hotkey} hotkey to: {new_key}")
        self.capturing_hotkey = None
        # Unbind the temporary capture binding.
        self.root.unbind_all("<Key>")
        return "break"
    
    def toggle_clicking(self):
        # If manually toggling off, cancel any set-click mode.
        self.clicking = not self.clicking
        if not self.clicking:
            self.set_clicks_remaining = None
        self.toggle_button.config(
            text=("Stop (" + self.start_key + ")" if self.clicking else "Start (" + self.start_key + ")")
        )
    
    def start_set_clicks(self):
        """Starts a session where a set number of clicks will be performed."""
        try:
            num_clicks = int(self.set_clicks_var.get())
            if num_clicks <= 0:
                return
        except ValueError:
            return
        
        # Set the number of remaining clicks and start clicking.
        self.set_clicks_remaining = num_clicks
        self.clicking = True
        self.toggle_button.config(text="Stop (" + self.start_key + ")")
    
    def auto_click(self):
        while True:
            if self.clicking:
                # Perform a left-click.
                self.mouse.click(Button.left)
                self.click_count += 1
                now = time.time()
                self.click_times.append(now)
                # Update the click counter label.
                self.counter_label.config(text=f"Clicks: {self.click_count}")
                
                # If in "set clicks" mode, count down.
                if self.set_clicks_remaining is not None:
                    self.set_clicks_remaining -= 1
                    if self.set_clicks_remaining <= 0:
                        self.clicking = False
                        self.set_clicks_remaining = None
                        self.toggle_button.config(text="Start (" + self.start_key + ")")
                
                time.sleep(self.interval_value.get())
            else:
                time.sleep(0.1)
    
    def update_cps(self):
        """Update the CPS label every 100ms based on clicks in the past second."""
        current_time = time.time()
        # Retain only the click timestamps from the last second.
        self.click_times = [t for t in self.click_times if current_time - t <= 1]
        cps = len(self.click_times)
        self.cps_label.config(text=f"CPS: {cps}")
        self.root.after(100, self.update_cps)
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AutoClickerGUI()
    app.run()
