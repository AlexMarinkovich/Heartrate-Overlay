from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QPlainTextEdit, QApplication, QLineEdit, QFileDialog
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt5.QtWinExtras import QWinTaskbarButton
import keyboard
import sys
import os

from device_finder import BleScanWorker
from hr_worker import HRRecorderWorker
from video_render_worker import VideoRenderWorker

MAX_LINES = 100  # max stored lines in console

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # --- Window ---
        self.setFixedSize(900, 600)
        self.setWindowTitle("Heartrate Overlay")
        self.setWindowIcon(QIcon("heartrate_overlay/assets/icon.ico"))
        main_layout = QHBoxLayout(self)

        # --- Console ---
        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: rgb(40, 40, 40); color: white;")
        self.console.setFont(QFont("Consolas", 10))
        main_layout.addWidget(self.console, stretch=1)

        # --- Button Panel ---
        button_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)

        BUTTON_WIDTH = 250
        BUTTON_HEIGHT = 40

        # --- TOP CONTROLS ---
        self.device_button = QPushButton("Find Devices")
        self.device_button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self.device_button.clicked.connect(self.find_devices)
        button_layout.addWidget(self.device_button)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter device address")
        self.text_input.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        button_layout.addWidget(self.text_input)
        self.load_device_address()
        self.text_input.textChanged.connect(self.save_device_address)

        self.button_one = QPushButton("Record Heartrate (F7)")
        self.button_one.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self.button_one.clicked.connect(self.toggle_recording)
        button_layout.addWidget(self.button_one)
        self.is_recording = False
        keyboard.add_hotkey("f7", self.toggle_recording)

        self.button_two = QPushButton("Generate Video")
        self.button_two.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self.button_two.clicked.connect(self.generate_video)
        button_layout.addWidget(self.button_two)

        button_layout.addStretch()  # Push everything above up

        # --- BOTTOM CONTROLS ---
        self.open_logs_button = QPushButton("Open Logs Folder")
        self.open_logs_button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self.open_logs_button.clicked.connect(lambda: self.open_folder("heartrate_overlay/logs"))
        button_layout.addWidget(self.open_logs_button)

        self.open_videos_button = QPushButton("Open Videos Folder")
        self.open_videos_button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        self.open_videos_button.clicked.connect(lambda: self.open_folder("heartrate_overlay/videos"))
        button_layout.addWidget(self.open_videos_button)

        clear_button = QPushButton("Clear Console")
        clear_button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
        clear_button.clicked.connect(self.console.clear)
        button_layout.addWidget(clear_button)

        

    # --- Fast, safe console logging ---
    def announce(self, text: str):
        self.console.appendPlainText(text)

        # Enforce max line count
        doc = self.console.document()
        while doc.blockCount() > MAX_LINES:
            cursor = self.console.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

        # Auto-scroll
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )

    def find_devices(self):
        self.announce("Scanning for BLE devices...")
        self.device_button.setEnabled(False)

        self.worker = BleScanWorker()
        self.worker.device_found.connect(self.announce)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.start()
    
    def on_scan_finished(self):
        self.announce("Scan complete.")
        self.device_button.setEnabled(True)

    def load_device_address(self):
        with open("heartrate_overlay/config/device_address.txt", "r") as f:
            self.text_input.setText(f.read().strip())

    def save_device_address(self):
        with open("heartrate_overlay/config/device_address.txt", "w") as f:
            f.write(self.text_input.text().strip())

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        address = self.text_input.text().strip()

        if not address:
            self.announce("❌ No device address set")
            return

        self.announce("▶ Starting heart rate recording...")
        self.button_one.setText("Stop Recording (F7)")
        self.is_recording = True

        self.taskbar_button.setOverlayIcon(self.overlay_connecting)
        
        self.hr_worker = HRRecorderWorker(address)
        self.hr_worker.log.connect(self.announce)
        self.hr_worker.finished.connect(self.on_recording_finished)
        self.hr_worker.connected.connect(self.on_hr_connected)
        self.hr_worker.start()

    def on_hr_connected(self):
        self.taskbar_button.setOverlayIcon(self.overlay_connected)
    
    def stop_recording(self):
        if self.hr_worker:
            self.announce("■ Stopping recording...")
            self.hr_worker.stop()

    def on_recording_finished(self):
        self.button_one.setText("Record Heartrate (F7)")
        self.is_recording = False
        self.hr_worker = None
        self.taskbar_button.clearOverlayIcon()

    def generate_video(self):
        logs_dir = "heartrate_overlay/logs"

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Heart Rate Log",
            logs_dir,
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        self.announce(f"Starting render:\n{file_path}")
        self.button_two.setEnabled(False)

        self.render_worker = VideoRenderWorker(file_path)

        self.render_worker.started.connect(
            lambda p: self.announce("Rendering started...")
        )

        self.render_worker.finished.connect(self.on_render_finished)
        self.render_worker.error.connect(self.on_render_error)

        self.render_worker.start()
    
    def on_render_finished(self, output_path: str):
        self.announce(f"Render saved to {output_path}")
        self.button_two.setEnabled(True)

    def on_render_error(self, message: str):
        self.announce(f"Render failed:\n{message}")
        self.button_two.setEnabled(True)

    def open_folder(self, relative_path: str):
        path = os.path.abspath(relative_path)
        os.makedirs(path, exist_ok=True)

        try:
            os.startfile(path)
        except Exception as e:
            self.announce(f"Failed to open folder:\n{e}")
            
    def create_dot_icon(self, color: str):
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("transparent"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QColor(color))
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()

        return QIcon(pixmap)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Taskbar Icon - must be AFTER window.show()
    window.taskbar_button = QWinTaskbarButton()
    window.taskbar_button.setWindow(window.windowHandle())
    window.overlay_connecting = window.create_dot_icon("orange")
    window.overlay_connected = window.create_dot_icon("red")

    sys.exit(app.exec_())