import re
import math
import logging

from Translation import tr, on_language_changed
import shiboken6


def _parse_parametric_to_graphic(content_str):
    from AutoEQ_Dialog import parse_parametric_to_graphic
    return parse_parametric_to_graphic(content_str)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QComboBox,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QDoubleSpinBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QPen, QPainterPath


class ForceDownComboBox(QComboBox):

    def showPopup(self):
        super().showPopup()
        popup = self.view().parentWidget()
        if popup:
            global_pos = self.mapToGlobal(self.rect().bottomLeft())
            popup.move(global_pos)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        arrow_w, arrow_h = 8, 5
        cx = self.width() - 10
        cy = self.height() // 2
        top = cy - arrow_h // 2
        bot = cy + arrow_h // 2
        left = cx - arrow_w // 2
        right = cx + arrow_w // 2
        painter.setBrush(QColor("#aaaaaa"))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon([QPointF(left, top), QPointF(right, top), QPointF(cx, bot)])
        painter.end()


class ArrowDoubleSpinBox(QDoubleSpinBox):

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        arrow_w, arrow_h = 7, 4
        cx = self.width() - 10
        up_cy = self.height() // 4
        down_cy = self.height() * 3 // 4

        painter.setBrush(QColor("#aaaaaa"))
        painter.setPen(Qt.NoPen)

        painter.drawPolygon([
            QPointF(cx, up_cy - arrow_h),
            QPointF(cx - arrow_w / 2, up_cy + arrow_h / 2),
            QPointF(cx + arrow_w / 2, up_cy + arrow_h / 2),
        ])

        painter.drawPolygon([
            QPointF(cx - arrow_w / 2, down_cy - arrow_h / 2),
            QPointF(cx + arrow_w / 2, down_cy - arrow_h / 2),
            QPointF(cx, down_cy + arrow_h),
        ])

        painter.end()


class RefreshButton(QPushButton):
    ICON_SIZE = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 0.0
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("btn_refresh_devices"))
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        self._anim_duration = 600
        self._anim_elapsed = 0

    def _on_anim_tick(self):
        self._anim_elapsed += self._anim_timer.interval()
        progress = min(self._anim_elapsed / self._anim_duration, 1.0)
        eased = 1.0 - (1.0 - progress) ** 3
        self._rotation = eased * 360.0
        self.update()
        if self._anim_elapsed >= self._anim_duration:
            self._anim_timer.stop()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._anim_timer.stop()
            self._anim_elapsed = 0
            self._rotation = 0.0
            self._anim_timer.start()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = self.ICON_SIZE / 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._rotation)
        painter.translate(-cx, -cy)

        color = QColor("#4da6ff") if self.underMouse() else QColor("#cccccc")
        pen = QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        arc_rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)

        arcs = [(45, 150), (225, 150)]
        for start, span in arcs:
            painter.drawArc(arc_rect, start * 16, span * 16)

        arrow_len = 2.5
        spread = math.radians(30)
        arrow_tips = [45, 225]

        for tip_deg in arrow_tips:
            tip_rad = math.radians(tip_deg)
            tip_x = cx + r * math.cos(tip_rad)
            tip_y = cy - r * math.sin(tip_rad)

            tan_rad = math.radians(tip_deg + 90)
            anchor_rad = tan_rad

            w1 = QPointF(tip_x + arrow_len * math.cos(anchor_rad - spread),
                         tip_y - arrow_len * math.sin(anchor_rad - spread))
            w2 = QPointF(tip_x + arrow_len * math.cos(anchor_rad + spread),
                         tip_y - arrow_len * math.sin(anchor_rad + spread))

            tip = QPointF(tip_x, tip_y)
            painter.drawLine(tip, w1)
            painter.drawLine(tip, w2)

        painter.restore()

    def _retranslate_ui(self):
        self.setToolTip(tr("btn_refresh_devices"))


class ToggleSwitch(QWidget):
    toggled = Signal(bool)
    stateChanged = Signal(int)

    SWITCH_WIDTH = 40
    TRACK_HEIGHT = 20
    THUMB_SIZE = 14
    THUMB_OFFSET = 3

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._checked = False
        self._text = text

        self._track_color_on = QColor("#0078D4")
        self._track_color_off = QColor("#3a3a3a")
        self._track_border_off = QColor("#555555")
        self._thumb_color = QColor("#ffffff")
        self._shadow_color = QColor(0, 0, 0, 40)

        font = self.font()
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text) + 8 if text else 0

        self.setFixedWidth(self.SWITCH_WIDTH + text_width)
        self.setFixedHeight(max(self.TRACK_HEIGHT + 8, fm.height() + 8))
        self.setCursor(Qt.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self.update()

    def setText(self, text):
        self._text = text
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.stateChanged.emit(int(self._checked))
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_y = (self.height() - self.TRACK_HEIGHT) / 2
        track_rect = QRectF(0, track_y, self.SWITCH_WIDTH, self.TRACK_HEIGHT)

        if self._checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._track_color_on)
        else:
            painter.setPen(self._track_border_off)
            painter.setBrush(self._track_color_off)
        painter.drawRoundedRect(track_rect, self.TRACK_HEIGHT / 2, self.TRACK_HEIGHT / 2)

        thumb_x = self.SWITCH_WIDTH - self.THUMB_SIZE - self.THUMB_OFFSET if self._checked else self.THUMB_OFFSET
        thumb_y = track_y + (self.TRACK_HEIGHT - self.THUMB_SIZE) / 2

        shadow_offset = 1.5
        shadow_rect = QRectF(thumb_x + shadow_offset, thumb_y + shadow_offset,
                             self.THUMB_SIZE, self.THUMB_SIZE)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._shadow_color)
        painter.drawEllipse(shadow_rect)

        thumb_rect = QRectF(thumb_x, thumb_y, self.THUMB_SIZE, self.THUMB_SIZE)
        painter.setBrush(self._thumb_color)
        painter.drawEllipse(thumb_rect)

        if self._text:
            painter.setPen(QColor("#cccccc"))
            text_x = self.SWITCH_WIDTH + 8
            text_rect = QRectF(text_x, 0, self.width() - text_x, self.height())
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self._text)

        painter.end()


class FrequencyBandWidget(QWidget):
    valueChanged = Signal(float)
    sliderReleased = Signal(float)
    freqChanged = Signal(float, float)

    def __init__(self, freq_hz, min_gain=-20.0, max_gain=20.0, step=0.1, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)

        try:
            self.freq_hz = float(freq_hz)
        except (ValueError, TypeError):
            self.freq_hz = 0.0
        self.min_gain = min_gain
        self.max_gain = max_gain
        self.step = step
        self._updating = False

        self.slider_factor = 10
        self.slider_min = int(min_gain * self.slider_factor)
        self.slider_max = int(max_gain * self.slider_factor)
        self.slider_step = int(step * self.slider_factor)

        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)

        self.hz_spinbox = ArrowDoubleSpinBox()
        self.hz_spinbox.setRange(1.0, 20000.0)
        self.hz_spinbox.setDecimals(1)
        self.hz_spinbox.setValue(self.freq_hz)
        self.hz_spinbox.setSuffix(" Hz")
        self.hz_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hz_spinbox.setFixedWidth(80)
        self.hz_spinbox.setStyleSheet("QDoubleSpinBox { font-weight: bold; }")
        self.hz_spinbox.editingFinished.connect(self._on_hz_editing_finished)
        layout.addWidget(self.hz_spinbox, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.slider = QSlider(Qt.Orientation.Vertical)
        self.slider.setRange(self.slider_min, self.slider_max)
        self.slider.setTickInterval(self.slider_step * 2)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.slider.setSingleStep(self.slider_step)
        self.slider.setPageStep(self.slider_step * 10)
        self.slider.sliderReleased.connect(self._on_slider_released)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.db_spinbox = ArrowDoubleSpinBox()
        self.db_spinbox.setRange(min_gain, max_gain)
        self.db_spinbox.setDecimals(1)
        self.db_spinbox.setSingleStep(step)
        self.db_spinbox.setSuffix(" dB")
        self.db_spinbox.setValue(0.0)
        self.db_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_spinbox.setFixedWidth(72)
        self.db_spinbox.valueChanged.connect(self._on_db_spinbox_changed)
        layout.addWidget(self.db_spinbox, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setLayout(layout)

    def _on_hz_editing_finished(self):
        if self._updating:
            return
        value = self.hz_spinbox.value()
        old_freq = self.freq_hz
        new_freq = round(value, 1)
        if abs(old_freq - new_freq) > 1e-6:
            self.freq_hz = new_freq
            self.freqChanged.emit(old_freq, new_freq)

    def _on_slider_changed(self, value):
        if self._updating:
            return
        gain = value / self.slider_factor
        self._updating = True
        self.db_spinbox.setValue(gain)
        self._updating = False

    def _on_slider_released(self):
        gain = self.get_gain()
        self.sliderReleased.emit(gain)

    def _on_db_spinbox_changed(self, value):
        if self._updating:
            return
        self._updating = True
        slider_value = int(round(value * self.slider_factor))
        slider_value = max(self.slider_min, min(self.slider_max, slider_value))
        self.slider.setValue(slider_value)
        self._updating = False
        self.sliderReleased.emit(value)

    def set_gain(self, gain_db):
        self._updating = True
        value = int(round(gain_db * self.slider_factor))
        value = max(self.slider_min, min(self.slider_max, value))
        self.slider.setValue(value)
        self.db_spinbox.setValue(gain_db)
        self._updating = False

    def set_freq(self, freq_hz):
        self._updating = True
        self.freq_hz = float(freq_hz)
        self.hz_spinbox.setValue(self.freq_hz)
        self._updating = False

    def get_gain(self):
        if not shiboken6.isValid(self.slider):
            return 0.0
        return self.slider.value() / self.slider_factor


class PreampWidget(QWidget):
    valueChanged = Signal(float)

    def __init__(self, min_gain=-20.0, max_gain=20.0, step=0.1, parent=None):
        super().__init__(parent)
        self.min_gain = min_gain
        self.max_gain = max_gain

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.preamp_label = QLabel(tr("label_preamp"))
        layout.addWidget(self.preamp_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_gain * 10), int(max_gain * 10))
        self.slider.setTickInterval(int(step * 20))
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        self.spinbox = ArrowDoubleSpinBox()
        self.spinbox.setRange(min_gain, max_gain)
        self.spinbox.setSingleStep(step)
        self.spinbox.setDecimals(1)
        self.spinbox.setSuffix(" dB")
        self.spinbox.setFixedWidth(72)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        layout.addWidget(self.spinbox)

        self.setLayout(layout)
        self._updating = False

    def _on_slider_changed(self, value):
        if self._updating:
            return
        self._updating = True
        gain = value / 10.0
        self.spinbox.setValue(gain)
        self._updating = False
        self.valueChanged.emit(gain)

    def _on_spinbox_changed(self, value):
        if self._updating:
            return
        self._updating = True
        self.slider.setValue(int(value * 10))
        self._updating = False
        self.valueChanged.emit(value)

    def set_gain(self, gain_db):
        self.spinbox.setValue(gain_db)

    def get_gain(self):
        return self.spinbox.value()

    def _retranslate_ui(self):
        self.preamp_label.setText(tr("label_preamp"))


class EQTab(QWidget):
    FREQS_15 = [25, 40, 63, 100, 160, 250, 400, 630, 1000,
                1600, 2500, 4000, 6300, 10000, 16000]
    FREQS_31 = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
                500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
                6300, 8000, 10000, 12500, 16000, 20000]
    _freq = 20.0
    _tmp = []
    while True:
        rounded = round(_freq, 1)
        if rounded > 50.0 + 1e-9:
            break
        _tmp.append(rounded)
        _freq *= 2 ** (1 / 12)
    DEFAULT_VARIABLE_FREQS = sorted(set(_tmp))

    anythingChanged = Signal()
    AutoEQRequested = Signal(str)
    ChannelBalanceRequested = Signal(str)
    monitorStateChanged = Signal(int)
    deviceRefreshRequested = Signal()

    def __init__(self, device_type, main_window, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.EQTab")
        self.device_type = device_type
        self.main_window = main_window
        self.current_freqs = self.FREQS_15
        self._variable_freqs = self.DEFAULT_VARIABLE_FREQS.copy()
        self.bands = []
        self._loading = False
        self._saved_device_name = None
        self.current_mode = '15频段'
        self._band_action_cooldown = False
        self._left_balance = 0.0
        self._right_balance = 0.0
        self._auto_eq_type = "GraphicEQ"
        self._auto_eq_raw_content = None

        self.monitor = None
        self._monitor_lock = None
        self._init_monitor()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        dev_layout = QHBoxLayout()
        self.enable_device = ToggleSwitch(tr("label_enable_device"))
        self.enable_device.setChecked(True)
        self.enable_device.stateChanged.connect(self._on_any_change)
        dev_layout.addWidget(self.enable_device)

        self.device_combo = ForceDownComboBox()
        self.device_combo.setMinimumWidth(250)
        self.device_combo.currentIndexChanged.connect(self._on_any_change)
        dev_layout.addWidget(self.device_combo)

        self.refresh_btn = RefreshButton()
        self.refresh_btn.clicked.connect(lambda: self.deviceRefreshRequested.emit())
        dev_layout.addWidget(self.refresh_btn)

        self.monitor_label = QLabel(tr("label_monitor"))
        dev_layout.addWidget(self.monitor_label)
        self.monitor_combo = ForceDownComboBox()
        self.monitor_combo.addItems([tr("label_monitor_off"), tr("label_monitor_on")])
        self.monitor_combo.setCurrentIndex(0)
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)
        dev_layout.addWidget(self.monitor_combo)

        dev_layout.addStretch()
        layout.addLayout(dev_layout)

        self.preamp = PreampWidget()
        self.preamp.valueChanged.connect(self._on_any_change)
        layout.addWidget(self.preamp)

        mode_layout = QHBoxLayout()
        self.graphiceq_label = QLabel(tr("label_graphic_eq"))
        mode_layout.addWidget(self.graphiceq_label)
        self.mode_combo = ForceDownComboBox()
        self.mode_combo.addItem(tr("mode_15band"), "15频段")
        self.mode_combo.addItem(tr("mode_31band"), "31频段")
        self.mode_combo.addItem(tr("mode_variable"), "可变频段")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        self.add_band_btn = QPushButton("+")
        self.add_band_btn.setFixedSize(30, 30)
        self.add_band_btn.clicked.connect(self._add_band)
        self.remove_band_btn = QPushButton("-")
        self.remove_band_btn.setFixedSize(30, 30)
        self.remove_band_btn.clicked.connect(self._remove_band)
        mode_layout.addWidget(self.add_band_btn)
        mode_layout.addWidget(self.remove_band_btn)

        self.import_bands_btn = QPushButton(tr("btn_import_bands"))
        self.import_bands_btn.clicked.connect(self._import_bands)
        self.import_bands_btn.setEnabled(False)
        mode_layout.addWidget(self.import_bands_btn)

        self.export_bands_btn = QPushButton(tr("btn_export_bands"))
        self.export_bands_btn.clicked.connect(self._export_bands)
        self.export_bands_btn.setEnabled(False)
        mode_layout.addWidget(self.export_bands_btn)

        self.AutoEQ_btn = QPushButton("AutoEQ")
        self.AutoEQ_btn.clicked.connect(lambda: self.AutoEQRequested.emit(self.device_type))
        mode_layout.addWidget(self.AutoEQ_btn)

        self.channel_balance_btn = QPushButton(tr("btn_channel_balance"))
        self.channel_balance_btn.clicked.connect(lambda: self.ChannelBalanceRequested.emit(self.device_type))
        mode_layout.addWidget(self.channel_balance_btn)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameStyle(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll_area)

        self._rebuild_bands(self.FREQS_15)
        self._update_band_buttons()

        on_language_changed(self._retranslate_ui)

    def _retranslate_ui(self):
        self.enable_device.setText(tr("label_enable_device"))
        self.monitor_label.setText(tr("label_monitor"))
        old_monitor_idx = self.monitor_combo.currentIndex()
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        self.monitor_combo.addItems([tr("label_monitor_off"), tr("label_monitor_on")])
        self.monitor_combo.setCurrentIndex(old_monitor_idx)
        self.monitor_combo.blockSignals(False)
        self.preamp._retranslate_ui()
        self.graphiceq_label.setText(tr("label_graphic_eq"))
        mode_index_map = {"15频段": 0, "31频段": 1, "可变频段": 2}
        old_mode_idx = mode_index_map.get(self.current_mode, 0)
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItem(tr("mode_15band"), "15频段")
        self.mode_combo.addItem(tr("mode_31band"), "31频段")
        self.mode_combo.addItem(tr("mode_variable"), "可变频段")
        self.mode_combo.setCurrentIndex(old_mode_idx)
        self.mode_combo.blockSignals(False)
        self.import_bands_btn.setText(tr("btn_import_bands"))
        self.export_bands_btn.setText(tr("btn_export_bands"))
        self.channel_balance_btn.setText(tr("btn_channel_balance"))
        self.refresh_btn._retranslate_ui()

    def _init_monitor(self):
        import threading
        self._monitor_lock = threading.Lock()

    def _update_band_buttons(self):
        if self.current_mode == '可变频段':
            self.add_band_btn.setEnabled(True)
            self.remove_band_btn.setEnabled(len(self._variable_freqs) > 0)
        else:
            self.add_band_btn.setEnabled(False)
            self.remove_band_btn.setEnabled(False)

    def _add_band(self):
        if self.current_mode != '可变频段':
            return
        if self._band_action_cooldown:
            return
        self._band_action_cooldown = True
        QTimer.singleShot(100, self._reset_band_cooldown)
        scroll_bar = self.scroll_area.horizontalScrollBar()
        old_pos = scroll_bar.value()

        gains = {band.freq_hz: band.get_gain() for band in self.bands}
        freqs = list(self._variable_freqs)
        new_freq = 0.0
        while new_freq in [round(f, 1) for f in freqs]:
            new_freq += 0.1
        freqs.append(new_freq)
        freqs.sort()
        self._rebuild_bands(freqs)
        for band in self.bands:
            if band.freq_hz in gains:
                band.set_gain(gains[band.freq_hz])
        self._variable_freqs = freqs
        self._update_band_buttons()
        new_max = scroll_bar.maximum()
        new_pos = min(old_pos, new_max)
        scroll_bar.setValue(new_pos)

    def _remove_band(self):
        if self.current_mode != '可变频段':
            return
        if self._band_action_cooldown:
            return
        self._band_action_cooldown = True
        QTimer.singleShot(100, self._reset_band_cooldown)
        freqs = list(self._variable_freqs)
        if not freqs:
            return

        scroll_bar = self.scroll_area.horizontalScrollBar()
        old_pos = scroll_bar.value()

        gains = {band.freq_hz: band.get_gain() for band in self.bands}
        min_freq = min(freqs)
        freqs.remove(min_freq)
        self._rebuild_bands(freqs)
        for band in self.bands:
            if band.freq_hz in gains:
                band.set_gain(gains[band.freq_hz])
        self._variable_freqs = freqs
        self._update_band_buttons()
        new_max = scroll_bar.maximum()
        new_pos = min(old_pos, new_max)
        scroll_bar.setValue(new_pos)
        self._on_any_change()

    def _reset_band_cooldown(self):
        self._band_action_cooldown = False

    def _on_monitor_changed(self, index):
        if self._loading:
            return
        if index == 1:
            self._start_monitor()
        else:
            self._stop_monitor()
        self.monitorStateChanged.emit(index)

    def _start_monitor(self):
        self.logger.info("尝试启动音频监听")
        mic_dev = self.main_window.get_input_audio_device()
        spk_dev = self.main_window.get_output_audio_device()

        if not mic_dev:
            QMessageBox.warning(self, tr("dialog_monitor_failed"), tr("msg_no_mic_selected"))
            self.monitor_combo.setCurrentIndex(0)
            self.logger.warning("监听失败: 未启用或未选择麦克风设备")
            return
        if not spk_dev:
            QMessageBox.warning(self, tr("dialog_monitor_failed"), tr("msg_no_speaker_selected"))
            self.monitor_combo.setCurrentIndex(0)
            self.logger.warning("监听失败: 未启用或未选择扬声器设备")
            return

        with self._monitor_lock:
            self._stop_monitor_locked()
            from AudioMonitor import AudioMonitor
            self.monitor = AudioMonitor(mic_dev, spk_dev, self._on_monitor_error)
            self.monitor.start()

    def _stop_monitor(self):
        with self._monitor_lock:
            self._stop_monitor_locked()

    def _stop_monitor_locked(self):
        if self.monitor:
            self.logger.info("停止音频监听")
            self.monitor.stop()
            self.monitor = None

    def _on_monitor_error(self, msg):
        self.logger.error(f"监听错误: {msg}")
        QMessageBox.warning(self, tr("dialog_monitor_error"), msg)
        self.monitor_combo.setCurrentIndex(0)
        with self._monitor_lock:
            self._stop_monitor_locked()

    def _rebuild_bands(self, freq_list):
        if hasattr(self, 'bands'):
            for band in self.bands:
                try:
                    band.sliderReleased.disconnect(self._on_any_change)
                except Exception:
                    pass
                try:
                    band.freqChanged.disconnect(self._on_band_freq_changed)
                except Exception:
                    pass

        new_container = QWidget()
        layout = QHBoxLayout(new_container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        new_bands = []
        for freq in freq_list:
            band = FrequencyBandWidget(freq)
            band.sliderReleased.connect(self._on_any_change)
            band.freqChanged.connect(self._on_band_freq_changed)
            new_bands.append(band)
            layout.addWidget(band)

        self.bands = new_bands
        self.bands_container = new_container
        self.scroll_area.setWidget(new_container)
        self.current_freqs = freq_list
        self.logger.debug(f"重建频段: {freq_list}")

    def _on_band_freq_changed(self, old_freq, new_freq):
        if self.current_mode in ('15频段', '31频段'):
            self.current_mode = '可变频段'
            self._variable_freqs = list(self.current_freqs)
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(2)
            self.mode_combo.blockSignals(False)
            self.import_bands_btn.setEnabled(True)
            self.export_bands_btn.setEnabled(True)

        freqs = list(self._variable_freqs)
        new_freq_rounded = round(new_freq, 1)
        for f in freqs:
            if abs(f - old_freq) < 0.05:
                continue
            if abs(f - new_freq_rounded) < 0.05:
                for band in self.bands:
                    if abs(band.freq_hz - old_freq) < 0.05:
                        band.set_freq(old_freq)
                        break
                return
        try:
            idx = next(i for i, f in enumerate(freqs) if abs(f - old_freq) < 0.05)
            freqs[idx] = new_freq_rounded
        except StopIteration:
            freqs.append(new_freq_rounded)
        freqs.sort()
        gains = {band.freq_hz: band.get_gain() for band in self.bands}
        scroll_bar = self.scroll_area.horizontalScrollBar()
        old_pos = scroll_bar.value()
        self._variable_freqs = freqs
        QTimer.singleShot(0, lambda: self._finish_band_freq_change(freqs, gains, old_pos))

    def _finish_band_freq_change(self, freqs, gains, old_pos):
        self._rebuild_bands(freqs)
        for band in self.bands:
            if band.freq_hz in gains:
                band.set_gain(gains[band.freq_hz])
        self._update_band_buttons()
        scroll_bar = self.scroll_area.horizontalScrollBar()
        new_max = scroll_bar.maximum()
        new_pos = min(old_pos, new_max)
        scroll_bar.setValue(new_pos)
        self._on_any_change()

    def _on_mode_changed(self, index):
        mode = self.mode_combo.itemData(index)
        if mode not in ("15频段", "31频段", "可变频段"):
            mode = ("15频段", "31频段", "可变频段")[index]
        current_gains = {}
        if hasattr(self, 'bands') and self.bands:
            current_gains = {band.freq_hz: band.get_gain() for band in self.bands}

        old_mode = self.current_mode
        if mode == "15频段":
            new_freqs = self.FREQS_15
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        elif mode == "31频段":
            new_freqs = self.FREQS_31
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        else:
            if self.current_mode in ('15频段', '31频段') and self.current_freqs:
                self._variable_freqs = list(self.current_freqs)
            elif not hasattr(self, '_variable_freqs') or not self._variable_freqs:
                self._variable_freqs = self.DEFAULT_VARIABLE_FREQS.copy()
            new_freqs = self._variable_freqs
            self.import_bands_btn.setEnabled(True)
            self.export_bands_btn.setEnabled(True)
        self.current_mode = mode
        self._rebuild_bands(new_freqs)
        if mode == '可变频段':
            for band in self.bands:
                if band.freq_hz in current_gains:
                    band.set_gain(current_gains[band.freq_hz])
        self._update_band_buttons()
        self._on_any_change()
        self.logger.info(f"均衡器模式切换为: {mode}")

    def _import_bands(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog_select_bands_file"), "", tr("file_filter_text"))
        if not file_path:
            return
        self.logger.info(f"导入频段文件: {file_path}")
        gain_map, preamp, eq_type, raw_content = self._parse_freq_gain_file(file_path)

        if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
            self._auto_eq_type = eq_type
            self._auto_eq_raw_content = raw_content
            main_win = self.main_window
            if main_win and hasattr(main_win, '_auto_eq_type'):
                main_win._auto_eq_type[self.device_type] = eq_type
                main_win._auto_eq_raw_content[self.device_type] = raw_content
            conv_preamp, conv_map = _parse_parametric_to_graphic(raw_content)
            if preamp is None:
                preamp = conv_preamp
            if conv_map and not gain_map:
                gain_map = conv_map
        elif eq_type == "GraphicEQ":
            self._auto_eq_type = "GraphicEQ"
            self._auto_eq_raw_content = None

        if gain_map:
            self.set_frequencies_from_gain_map(gain_map)
        self.preamp.set_gain(preamp if preamp is not None else 0.0)
        if not gain_map and preamp is None:
            QMessageBox.warning(self, tr("dialog_import_failed"), tr("msg_no_freq_gain_data"))
            return
        self._on_any_change()

    def _export_bands(self):
        eq_type = self._auto_eq_type
        preamp = self.preamp.get_gain()

        if eq_type in ("ParametricEQ", "FixedBandEQ") and self._auto_eq_raw_content:
            lines = []
            if abs(preamp) > 1e-6:
                lines.append(f"Preamp: {preamp:.1f} dB\n")
            for line in self._auto_eq_raw_content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                lower = stripped.lower()
                if lower.startswith('preamp:') or lower.startswith('device:'):
                    continue
                lines.append(stripped + "\n")
        elif self.current_mode == '可变频段':
            pairs = []
            for band in self.bands:
                freq = band.freq_hz
                gain = band.get_gain()
                if abs(freq - round(freq)) < 1e-6:
                    freq_str = str(int(round(freq)))
                else:
                    freq_str = f"{freq:.1f}"
                gain_str = f"{gain:+.1f}"
                pairs.append(f"{freq_str} {gain_str}")
            lines = []
            if abs(preamp) > 1e-6:
                lines.append(f"Preamp: {preamp:.1f} dB\n")
            lines.append("GraphicEQ: " + "; ".join(pairs) + "\n")
        else:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialog_export_bands"),
            "",
            tr("file_filter_txt")
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            self.logger.info(f"已导出 {eq_type} 频段到 {file_path}")
            QMessageBox.information(self, tr("dialog_export_success"), tr("msg_file_saved_to", path=file_path))
        except Exception as e:
            self.logger.exception(f"导出失败: {e}")
            QMessageBox.warning(self, tr("dialog_export_failed"), tr("msg_cannot_write_file", error=str(e)))

    def _parse_freq_gain_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.logger.exception(f"读取文件失败: {file_path}")
            return None, None, "GraphicEQ", None
        return self._parse_freq_gain_from_text(content)

    def _parse_freq_gain_from_text(self, content):
        gain_map = {}
        preamp = None
        eq_type = "GraphicEQ"
        raw_content = None
        lines = content.splitlines()
        raw_lines = []

        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            if 'preamp:' in line_lower:
                parts = line_stripped.split()
                for part in parts:
                    try:
                        preamp = float(part)
                        break
                    except ValueError:
                        continue

            if line_lower.startswith('filter '):
                raw_lines.append(line)
                if eq_type == "GraphicEQ":
                    eq_type = "ParametricEQ"

        if raw_lines:
            raw_content = '\n'.join(raw_lines) + '\n'
            _, gain_map = _parse_parametric_to_graphic(raw_content)
            self.logger.info(f"导入 {eq_type}: {len(raw_lines)} 条 Filter")
            return gain_map, preamp, eq_type, raw_content

        for line in lines:
            line_lower = line.lower()
            if "graphiceq:" in line_lower:
                after_colon = line.split("GraphicEQ:", 1)[1].strip()
                pairs = after_colon.split(';')
                for pair in pairs:
                    pair = pair.strip()
                    if not pair:
                        continue
                    parts = pair.split()
                    if len(parts) >= 2:
                        try:
                            freq = float(parts[0])
                            gain = float(parts[1])
                            gain_map[freq] = gain
                        except ValueError:
                            continue
                if gain_map:
                    eq_type = "GraphicEQ"
                    break

        if not gain_map:
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        freq = float(parts[0])
                        gain = float(parts[1])
                        gain_map[freq] = gain
                    except ValueError:
                        continue
        eq_type = "GraphicEQ"
        self.logger.debug(f"解析得到 {len(gain_map)} 个频率-增益点, preamp={preamp}")
        return gain_map, preamp, eq_type, raw_content

    def _on_any_change(self, value=None):
        if not self._loading:
            self.anythingChanged.emit()

    def set_device_list(self, devices):
        self.device_combo.clear()
        for dev in devices:
            self.device_combo.addItem(dev.description(), dev)
        if self.device_combo.count() == 0:
            self.device_combo.addItem(tr("label_no_device_found"))
        if self._saved_device_name:
            self.set_device_by_name(self._saved_device_name)

    def get_device_id(self):
        if not self.enable_device.isChecked():
            return None
        data = self.device_combo.currentData()
        if data is None:
            return self._saved_device_name
        if hasattr(data, 'id'):
            dev_id = data.id()
            if hasattr(dev_id, 'data'):
                id_str = bytes(dev_id).decode('utf-8', errors='ignore')
            elif isinstance(dev_id, bytes):
                id_str = dev_id.decode('utf-8', errors='ignore')
            else:
                id_str = str(dev_id)
            guid = self._extract_guid(id_str)
            return guid if guid else id_str
        return str(data)

    def get_audio_device(self):
        if not self.enable_device.isChecked():
            return None
        data = self.device_combo.currentData()
        if hasattr(data, 'description'):
            return data
        return None

    def get_device_name(self):
        if not self.enable_device.isChecked():
            return None
        current_text = self.device_combo.currentText()
        if current_text.endswith(tr("label_unavailable")) or current_text == tr("label_no_device_found"):
            return self._saved_device_name
        return current_text

    def is_device_enabled(self):
        return self.enable_device.isChecked()

    def set_device_enabled(self, enabled):
        self.enable_device.setChecked(enabled)

    def set_device_by_name(self, name):
        self._saved_device_name = name
        if name:
            for i in range(self.device_combo.count()):
                data = self.device_combo.itemData(i)
                if data is None:
                    continue
                if hasattr(data, 'id'):
                    dev_id = data.id()
                    if hasattr(dev_id, 'data'):
                        id_str = bytes(dev_id).decode('utf-8', errors='ignore')
                    elif isinstance(dev_id, bytes):
                        id_str = dev_id.decode('utf-8', errors='ignore')
                    else:
                        id_str = str(dev_id)
                    guid = self._extract_guid(id_str)
                    if (guid and guid == name) or id_str == name:
                        self.device_combo.setCurrentIndex(i)
                        self.enable_device.setChecked(True)
                        return True
                else:
                    if str(data) == name:
                        self.device_combo.setCurrentIndex(i)
                        self.enable_device.setChecked(True)
                        return True
            name_lower = name.lower()
            for i in range(self.device_combo.count()):
                text = self.device_combo.itemText(i).lower()
                if name_lower in text:
                    self.device_combo.setCurrentIndex(i)
                    self.enable_device.setChecked(True)
                    return True
            self.device_combo.addItem(f"{name}{tr('label_unavailable')}")
            self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
            self.enable_device.setChecked(True)
            return True
        self.enable_device.setChecked(False)
        return False

    def get_preamp_gain(self):
        return self.preamp.get_gain()

    def set_preamp_gain(self, gain):
        self.preamp.set_gain(gain)

    def get_filter_gains(self):
        freqs = [band.freq_hz for band in self.bands if band.freq_hz > 0.5]
        gains = [band.get_gain() for band in self.bands if band.freq_hz > 0.5]
        return freqs, gains

    def get_channel_balance(self):
        return self._left_balance, self._right_balance

    def set_channel_balance(self, left_gain, right_gain):
        self._left_balance = left_gain
        self._right_balance = right_gain
        self._on_any_change()

    def set_filter_gains(self, freq_gain_map):
        self._loading = True
        self.bands_container.setUpdatesEnabled(False)
        for band in self.bands:
            if band.freq_hz in freq_gain_map:
                band.set_gain(freq_gain_map[band.freq_hz])
            else:
                band.set_gain(0.0)
        self.bands_container.setUpdatesEnabled(True)
        self._loading = False

    def set_frequencies_from_gain_map(self, gain_map):
        if not gain_map:
            self.set_mode_and_freqs('15频段')
            return
        converted_map = {}
        for k, v in gain_map.items():
            try:
                freq = float(k)
                converted_map[freq] = v
            except (ValueError, TypeError):
                continue
        if not converted_map:
            self.set_mode_and_freqs('15频段')
            return
        freq_list = sorted(converted_map.keys())
        if set(freq_list) == set(self.FREQS_15):
            self.current_mode = '15频段'
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        elif set(freq_list) == set(self.FREQS_31):
            self.current_mode = '31频段'
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        else:
            self.current_mode = '可变频段'
            self.import_bands_btn.setEnabled(True)
            self.export_bands_btn.setEnabled(True)
            self._variable_freqs = freq_list

        self._rebuild_bands(freq_list)
        self.set_filter_gains(converted_map)

        self.mode_combo.blockSignals(True)
        if self.current_mode == '15频段':
            self.mode_combo.setCurrentIndex(0)
        elif self.current_mode == '31频段':
            self.mode_combo.setCurrentIndex(1)
        else:
            self.mode_combo.setCurrentIndex(2)
        self.mode_combo.blockSignals(False)
        self._update_band_buttons()

    def set_mode_and_freqs(self, mode, variable_freqs=None):
        self._loading = True
        mode = mode.strip()
        if mode == '15频段':
            mode = '15频段'
        elif mode == '31频段':
            mode = '31频段'

        if mode == '15频段':
            freq_list = self.FREQS_15
            combo_index = 0
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        elif mode == '31频段':
            freq_list = self.FREQS_31
            combo_index = 1
            self.import_bands_btn.setEnabled(False)
            self.export_bands_btn.setEnabled(False)
        elif mode == '可变频段':
            if variable_freqs is not None:
                freq_list = variable_freqs
            else:
                freq_list = self._variable_freqs
            combo_index = 2
            self.import_bands_btn.setEnabled(True)
            self.export_bands_btn.setEnabled(True)
        else:
            self._loading = False
            logging.warning(f"未知模式 '{mode}'，已切换至15频段")
            self.set_mode_and_freqs('15频段', None)
            return

        self._rebuild_bands(freq_list)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(combo_index)
        self.mode_combo.blockSignals(False)
        if mode == '可变频段' and variable_freqs is not None:
            self._variable_freqs = variable_freqs
        self.current_mode = mode
        self._update_band_buttons()
        self._loading = False

    def reset_to_default(self):
        self._loading = True
        self.enable_device.setChecked(False)
        self.preamp.set_gain(0.0)
        self.mode_combo.setCurrentIndex(0)
        self._rebuild_bands(self.FREQS_15)
        for band in self.bands:
            band.set_gain(0.0)
        self._variable_freqs = self.DEFAULT_VARIABLE_FREQS.copy()
        self._saved_device_name = None
        self.current_mode = '15频段'
        self.monitor_combo.setCurrentIndex(0)
        self._stop_monitor()
        self._update_band_buttons()
        self._left_balance = 0.0
        self._right_balance = 0.0
        self._loading = False
        self.logger.info("标签页已重置为默认值")

    def _extract_guid(self, text):
        match = re.search(r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}', text)
        return match.group(0) if match else None