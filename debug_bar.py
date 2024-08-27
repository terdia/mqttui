import time
import psutil
from flask import request
from threading import Lock
import logging

class DebugBarPanel:
    def __init__(self, name):
        self.name = name
        self.data = {}

    def record(self, key, value):
        self.data[key] = value

    def get_data(self):
        return self.data

class DebugBar:
    def __init__(self):
        self.panels = {}
        self.enabled = False
        self.start_time = None
        self.lock = Lock()
        try:
            self.process = psutil.Process()
        except Exception as e:
            logging.error(f"Failed to initialize psutil Process: {e}")
            self.process = None

    def add_panel(self, name):
        with self.lock:
            if name not in self.panels:
                self.panels[name] = DebugBarPanel(name)

    def record(self, panel, key, value):
        with self.lock:
            if panel in self.panels:
                self.panels[panel].record(key, value)

    def start_request(self):
        self.start_time = time.time()

    def end_request(self):
        if self.start_time:
            duration = time.time() - self.start_time
            self.record('request', 'duration', f"{duration:.2f}s")
            self.start_time = None

    def get_data(self):
        with self.lock:
            #self.update_performance_metrics()
            return {name: panel.get_data() for name, panel in self.panels.items()}

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def remove(self, panel_name, key):
        with self.lock:
            if panel_name in self.panels:
                panel = self.panels[panel_name]
                if key in panel.data:
                    del panel.data[key]

debug_bar = DebugBar()

# Initialize default panels
debug_bar.add_panel('mqtt')
debug_bar.add_panel('request')
debug_bar.add_panel('performance')

def debug_bar_middleware():
    debug_bar.start_request()
    debug_bar.record('request', 'path', request.path)
    debug_bar.record('request', 'method', request.method)