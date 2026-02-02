import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from hr_recorder import record_heartrate

class HRRecorderWorker(QThread):
    log = pyqtSignal(str)
    finished = pyqtSignal()
    connected = pyqtSignal()

    def __init__(self, address):
        super().__init__()
        self.address = address
        self._stop_event = asyncio.Event()

    def run(self):
        asyncio.run(
            record_heartrate(
                self.address,
                self._stop_event,
                log_callback=self.handle_log
            )
        )
        self.finished.emit()

    def handle_log(self, text: str):
        self.log.emit(text)

        # Detect successful connection
        if text == "Connected to Polar H10":
            self.connected.emit()

    def stop(self):
        self._stop_event.set()
