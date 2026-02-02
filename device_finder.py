from PyQt5.QtCore import QThread, pyqtSignal
import asyncio
from bleak import BleakScanner

class BleScanWorker(QThread):
    device_found = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        asyncio.run(self.scan())

    async def scan(self):
        devices = await BleakScanner.discover(timeout=5)
        for d in devices:
            name = d.name or "Unknown"
            self.device_found.emit(f"{d.address} {name}")
        self.finished.emit()