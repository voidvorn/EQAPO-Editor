import sys
import logging
from pathlib import Path

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from Graphic_EQualizer import ArrowDoubleSpinBox

from Translation import tr, on_language_changed


class ChannelBalanceDialog(QDialog):
    balanceChanged = Signal(float, float)

    def __init__(self, left_gain=0.0, right_gain=0.0, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.ChannelBalanceDialog")
        self.setWindowTitle(tr("dialog_channel_balance_title"))
        self.setFixedSize(420, 200)
        self.setModal(False)

        try:
            icon_path = APP_DIR / "EQAPO_Editor.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            self.logger.error(f"设置窗口图标时出错: {e}")

        self._left_gain = left_gain
        self._right_gain = right_gain
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(8)

        layout.addStretch()

        balance_layout, self.balance_label, self.balance_slider, self.balance_spinbox = self._create_balance_row(
            tr("label_balance"),
            self._on_balance_slider_changed, self._on_balance_spinbox_changed
        )
        layout.addLayout(balance_layout)

        left_layout, self.left_label, self.left_slider, self.left_spinbox = self._create_channel_row(
            tr("label_left_channel"), self._left_gain,
            self._on_left_slider_changed, self._on_left_spinbox_changed
        )
        layout.addLayout(left_layout)

        right_layout, self.right_label, self.right_slider, self.right_spinbox = self._create_channel_row(
            tr("label_right_channel"), self._right_gain,
            self._on_right_slider_changed, self._on_right_spinbox_changed
        )
        layout.addLayout(right_layout)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.reset_btn = QPushButton(tr("btn_reset"))
        self.reset_btn.clicked.connect(self._reset_balance)
        button_layout.addWidget(self.reset_btn)
        layout.addLayout(button_layout)

        self._sync_balance_slider()

        on_language_changed(self._retranslate_ui)


    def _create_balance_row(self, label_text, slider_callback, spinbox_callback):
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setFixedWidth(60)
        label.setStyleSheet("color: #cccccc; font-size: 10pt;")
        row.addWidget(label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(-200, 200)
        slider.setValue(0)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(10)
        slider.valueChanged.connect(slider_callback)
        row.addWidget(slider)

        spinbox = ArrowDoubleSpinBox()
        spinbox.setRange(-20.0, 20.0)
        spinbox.setSingleStep(0.1)
        spinbox.setDecimals(1)
        spinbox.setSuffix(" dB")
        spinbox.setValue(0.0)
        spinbox.setFixedWidth(72)
        spinbox.valueChanged.connect(spinbox_callback)
        row.addWidget(spinbox)

        return row, label, slider, spinbox

    def _create_channel_row(self, label_text, initial_value, slider_callback, spinbox_callback):
        row = QHBoxLayout()
        row.setSpacing(10)

        label = QLabel(label_text)
        label.setFixedWidth(60)
        label.setStyleSheet("color: #cccccc; font-size: 10pt;")
        row.addWidget(label)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(-200, 200)
        slider.setValue(int(initial_value * 10))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(10)
        slider.valueChanged.connect(slider_callback)
        row.addWidget(slider)

        spinbox = ArrowDoubleSpinBox()
        spinbox.setRange(-20.0, 20.0)
        spinbox.setSingleStep(0.1)
        spinbox.setDecimals(1)
        spinbox.setSuffix(" dB")
        spinbox.setValue(initial_value)
        spinbox.setFixedWidth(72)
        spinbox.valueChanged.connect(spinbox_callback)
        row.addWidget(spinbox)

        return row, label, slider, spinbox


    def _on_left_slider_changed(self, value):
        if self._updating:
            return
        gain = value / 10.0
        self._updating = True
        self._left_gain = gain
        self.left_spinbox.blockSignals(True)
        self.left_spinbox.setValue(gain)
        self.left_spinbox.blockSignals(False)
        self._sync_balance_slider()
        self._updating = False
        self._emit_balance()

    def _on_left_spinbox_changed(self, value):
        if self._updating:
            return
        self._updating = True
        self._left_gain = value
        self.left_slider.blockSignals(True)
        self.left_slider.setValue(int(value * 10))
        self.left_slider.blockSignals(False)
        self._sync_balance_slider()
        self._updating = False
        self._emit_balance()


    def _on_right_slider_changed(self, value):
        if self._updating:
            return
        gain = value / 10.0
        self._updating = True
        self._right_gain = gain
        self.right_spinbox.blockSignals(True)
        self.right_spinbox.setValue(gain)
        self.right_spinbox.blockSignals(False)
        self._sync_balance_slider()
        self._updating = False
        self._emit_balance()

    def _on_right_spinbox_changed(self, value):
        if self._updating:
            return
        self._updating = True
        self._right_gain = value
        self.right_slider.blockSignals(True)
        self.right_slider.setValue(int(value * 10))
        self.right_slider.blockSignals(False)
        self._sync_balance_slider()
        self._updating = False
        self._emit_balance()


    def _on_balance_slider_changed(self, value):
        if self._updating:
            return
        balance = value / 10.0
        self._updating = True
        self.balance_spinbox.blockSignals(True)
        self.balance_spinbox.setValue(balance)
        self.balance_spinbox.blockSignals(False)
        self._apply_balance(balance)
        self._sync_channel_widgets()
        self._updating = False
        self._emit_balance()

    def _on_balance_spinbox_changed(self, value):
        if self._updating:
            return
        self._updating = True
        self.balance_slider.blockSignals(True)
        self.balance_slider.setValue(int(value * 10))
        self.balance_slider.blockSignals(False)
        self._apply_balance(value)
        self._sync_channel_widgets()
        self._updating = False
        self._emit_balance()


    def _apply_balance(self, balance):
        self._left_gain = -balance
        self._right_gain = balance

    def _sync_balance_slider(self):
        balance = (self._right_gain - self._left_gain) / 2.0
        self.balance_slider.blockSignals(True)
        self.balance_slider.setValue(int(balance * 10))
        self.balance_slider.blockSignals(False)
        self.balance_spinbox.blockSignals(True)
        self.balance_spinbox.setValue(balance)
        self.balance_spinbox.blockSignals(False)

    def _sync_channel_widgets(self):
        self.left_slider.blockSignals(True)
        self.left_slider.setValue(int(self._left_gain * 10))
        self.left_slider.blockSignals(False)
        self.left_spinbox.blockSignals(True)
        self.left_spinbox.setValue(self._left_gain)
        self.left_spinbox.blockSignals(False)

        self.right_slider.blockSignals(True)
        self.right_slider.setValue(int(self._right_gain * 10))
        self.right_slider.blockSignals(False)
        self.right_spinbox.blockSignals(True)
        self.right_spinbox.setValue(self._right_gain)
        self.right_spinbox.blockSignals(False)

    def _emit_balance(self):
        self.balanceChanged.emit(self._left_gain, self._right_gain)

    def _reset_balance(self):
        self._updating = True
        self._left_gain = 0.0
        self._right_gain = 0.0

        self.balance_slider.setValue(0)
        self.balance_spinbox.setValue(0.0)
        self.left_slider.setValue(0)
        self.left_spinbox.setValue(0.0)
        self.right_slider.setValue(0)
        self.right_spinbox.setValue(0.0)

        self._updating = False
        self._emit_balance()

    def get_balance(self):
        return self._left_gain, self._right_gain

    def _retranslate_ui(self):
        self.setWindowTitle(tr("dialog_channel_balance_title"))
        self.balance_label.setText(tr("label_balance"))
        self.left_label.setText(tr("label_left_channel"))
        self.right_label.setText(tr("label_right_channel"))
        self.reset_btn.setText(tr("btn_reset"))