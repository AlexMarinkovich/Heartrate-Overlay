from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont

class QRangeSlider(QWidget):
    rangeChanged = pyqtSignal(int, int)

    def __init__(
        self,
        minimum=0,
        maximum=100,
        parent=None,
        initial_low=None,
        initial_high=None,
        left_color=QColor(80, 80, 80),
        middle_color=QColor(0, 170, 255),
        right_color=QColor(80, 80, 80),
        handle_color=QColor("gray"),
        text_color=QColor("black"),
        font_size=8,
    ):
        super().__init__(parent)

        self.min = minimum
        self.max = maximum

        # ---- Initialize pins safely ----
        if initial_low is None:
            initial_low = self.min
        if initial_high is None:
            initial_high = self.max

        self.low = max(self.min, min(initial_low, self.max))
        self.high = max(self.low, min(initial_high, self.max))

        self.left_color = left_color
        self.middle_color = middle_color
        self.right_color = right_color
        self.handle_color = handle_color
        self.text_color = text_color

        self.handle_radius = 7
        self.dragging = None

        self.setFont(QFont("Arial Narrow", font_size))
        self.setFixedHeight(44)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        y = h // 2 + 6
        r = self.handle_radius

        painter.setPen(Qt.NoPen)

        def x_from_value(v):
            return int((v - self.min) / (self.max - self.min) * (w - 2*r)) + r

        low_x = x_from_value(self.low)
        high_x = x_from_value(self.high)

        # ---- Track segments ----
        painter.setBrush(self.left_color)
        painter.drawRect(r, y - 2, low_x - r, 6)

        painter.setBrush(self.middle_color)
        painter.drawRect(low_x, y - 3, high_x - low_x, 6)

        painter.setBrush(self.right_color)
        painter.drawRect(high_x, y - 2, w - r - high_x, 6)

        # ---- Handles ----
        painter.setBrush(self.handle_color)
        painter.drawEllipse(QRect(low_x - r, y - r, 2*r, 2*r))
        painter.drawEllipse(QRect(high_x - r, y - r, 2*r, 2*r))

        # ---- Text ----
        painter.setPen(self.text_color)
        fm = painter.fontMetrics()

        # Handle labels
        low_text = str(self.low)
        high_text = str(self.high)

        painter.drawText(
            low_x - fm.width(low_text) // 2,
            14,
            low_text,
        )
        painter.drawText(
            high_x - fm.width(high_text) // 2,
            14,
            high_text,
        )

    def mousePressEvent(self, event):
        x = event.x()
        w = self.width()
        r = self.handle_radius

        def x_from_value(v):
            return (v - self.min) / (self.max - self.min) * (w - 2*r) + r

        low_x = x_from_value(self.low)
        high_x = x_from_value(self.high)

        self.dragging = "low" if abs(x - low_x) < abs(x - high_x) else "high"

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return

        w = self.width()
        r = self.handle_radius

        value = self.min + (event.x() - r) / (w - 2*r) * (self.max - self.min)
        value = int(max(self.min, min(self.max, value)))

        if self.dragging == "low":
            self.low = min(value, self.high)
        else:
            self.high = max(value, self.low)

        self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = None
        self.rangeChanged.emit(self.low, self.high)
