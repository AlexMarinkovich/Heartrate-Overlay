from PyQt5.QtCore import QThread, pyqtSignal
from video_renderer import render_video

class VideoRenderWorker(QThread):
    started = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, csv_path: str, hr_interval_1: int, hr_interval_2: int):
        super().__init__()
        self.csv_path = csv_path
        self.hr_interval_1 = hr_interval_1
        self.hr_interval_2 = hr_interval_2

    def run(self):
        try:
            self.started.emit(self.csv_path)
            output_path = render_video(self.csv_path, self.hr_interval_1, self.hr_interval_2)
            self.finished.emit(output_path)
        except Exception as e:
            self.error.emit(str(e))
