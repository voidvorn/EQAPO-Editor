import sys
import re
import time
import logging
import json
import ctypes
import traceback
from ctypes import wintypes
from pathlib import Path
import signal
import shutil
import uuid
import subprocess

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()

def setup_logging():
    log_dir = APP_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    main_log = log_dir / "Routine.log"
    error_log = log_dir / "Wrong.log"
    download_log = log_dir / "Downloads.log"

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s'
    )

    main_handler = logging.FileHandler(main_log, encoding='utf-8')
    main_handler.setLevel(logging.DEBUG)
    main_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(error_log, encoding='utf-8', delay=True)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)

    download_logger = logging.getLogger('download')
    download_logger.setLevel(logging.DEBUG)
    download_logger.propagate = False
    download_handler = logging.FileHandler(download_log, encoding='utf-8', delay=True)
    download_handler.setFormatter(formatter)
    download_logger.addHandler(download_handler)

    for lib in ['urllib3', 'requests', 'requests.packages.urllib3']:
        lib_logger = logging.getLogger(lib)
        lib_logger.setLevel(logging.DEBUG)
        lib_logger.propagate = False
        lib_logger.addHandler(download_handler)

    return root_logger

_logger = setup_logging()
_logger.info("应用程序启动，日志系统初始化完成")

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QMessageBox,
        QFrame, QScrollArea, QLineEdit,
        QTabWidget, QDialog, QStyle,
        QDialogButtonBox, QSystemTrayIcon, QMenu, QComboBox, QWidgetAction, QSizePolicy
    )
    from PySide6.QtCore import (
        Qt, QTimer, QFileSystemWatcher, QThreadPool,
        QEvent, QPoint, QPointF, QUrl, QDir, QPropertyAnimation,
        QEasingCurve, QSize, QBuffer, QByteArray
    )
    from PySide6.QtGui import QAction, QPalette, QColor, QCursor, QIcon, QDesktopServices, QPainter, QPixmap, QPen

    import queue

    from Graphic_EQualizer import EQTab, ToggleSwitch, ForceDownComboBox
    from AutoEQ_Dialog import AutoEQDialog
    from ChannelBalance_Dialog import ChannelBalanceDialog
    from Custom_window import CustomWindow, get_icon_path, lock_temp_resources
    from Automatic_startup import AutomaticStartup

    from Translation import tr, on_language_changed, set_language, install_qt_translator

    def _toggle_set_text(self, text):
        self._text = text
        self.update()
    ToggleSwitch.setText = _toggle_set_text

    from auto_config_switch import config_manager
    from app_config_manager import app_config_manager, RESIDENT_KEY
    from app_detector import AppDetector
    from process_detector import ProcessDetector, get_detector, ProcessInfo
    from extensions_manager import ExtensionsPage

except Exception as _import_error:
    _logger.critical("启动时导入模块失败，程序无法继续运行", exc_info=True)
    traceback.print_exc()
    sys.exit(1)


def extract_guid(text):
    match = re.search(r'\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}', text)
    return match.group(0) if match else None

_app_window = None

class NotificationPopup(QWidget):
    _active_popups = []

    def __init__(self, title, message, duration=5000, parent=None, app_icon=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.SubWindow
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)

        self._parent = parent
        self._duration = duration
        self._auto_close_timer = None

        self._setup_ui(title, message, app_icon)
        self._position_bottom_right()
        self._animate_in(duration)

    @classmethod
    def show_notification(cls, title, message, duration=5000, parent=None, app_icon=None):
        for popup in cls._active_popups:
            try:
                popup.close()
            except RuntimeError:
                pass
        cls._active_popups.clear()

        popup = cls(title, message, duration, parent, app_icon)
        cls._active_popups.append(popup)
        popup.show()

    def _setup_ui(self, title, message, app_icon=None):
        self.setFixedSize(320, 80)

        container = QFrame(self)
        container.setObjectName("notificationContainer")
        container.setGeometry(0, 0, 320, 80)
        container.setStyleSheet("""
            QFrame#notificationContainer {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        icon_label = QLabel()
        icon_label.setFixedSize(20, 20)
        own_icon = get_icon_path()
        if own_icon:
            icon_label.setPixmap(QIcon(str(own_icon)).pixmap(20, 20))
        else:
            icon_label.setText("🔔")
            icon_label.setStyleSheet("font-size: 14px;")
        title_row.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #ffffff;
            font-size: 11pt;
            font-weight: bold;
        """)
        title_row.addWidget(title_label)
        title_row.addStretch()

        layout.addLayout(title_row)

        if app_icon and not app_icon.isNull():
            icon_row = QHBoxLayout()
            icon_row.setSpacing(6)
            app_icon_label = QLabel()
            app_icon_label.setFixedSize(28, 28)
            app_icon_label.setPixmap(app_icon.pixmap(28, 28))
            icon_row.addWidget(app_icon_label)
            if message:
                msg_label = QLabel(message)
                msg_label.setStyleSheet("""
                    color: #aaaaaa;
                    font-size: 9pt;
                """)
                icon_row.addWidget(msg_label)
            icon_row.addStretch()
            layout.addLayout(icon_row)
        else:
            msg_label = QLabel(message)
            msg_label.setStyleSheet("""
                color: #aaaaaa;
                font-size: 9pt;
            """)
            msg_label.setWordWrap(True)
            layout.addWidget(msg_label)

    def _position_bottom_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = screen_geo.right() - self.width() - 20
            y = screen_geo.bottom() - self.height() - 20
            self.move(x, y)

    def _animate_in(self, duration):
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._animate_out)
        self._auto_close_timer.start(duration)

    def _animate_out(self):
        self._auto_close_timer = None
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.close)
        anim.start()

    def enterEvent(self, event):
        if self._auto_close_timer and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._auto_close_timer:
            self._auto_close_timer.start(5000)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._parent:
            if self._parent.isVisible():
                self._parent.hide()
                if hasattr(self._parent, 'show_hide_btn'):
                    self._parent.show_hide_btn.setText(tr("tray_show"))
            else:
                self._parent.show()
                self._parent.raise_()
                self._parent.activateWindow()
                if hasattr(self._parent, 'show_hide_btn'):
                    self._parent.show_hide_btn.setText(tr("tray_hide"))
        self._animate_out()
        super().mousePressEvent(event)

    def closeEvent(self, event):
        if self in NotificationPopup._active_popups:
            NotificationPopup._active_popups.remove(self)
        super().closeEvent(event)


def _create_speaker_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#cccccc"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    cone = [
        QPoint(2, 5),
        QPoint(2, 11),
        QPoint(7, 13),
        QPoint(7, 3),
    ]
    painter.drawPolygon(cone)

    painter.drawRect(7, 3, 3, 10)

    painter.drawArc(11, 4, 3, 8, -70 * 16, 140 * 16)
    painter.drawArc(13, 2, 3, 12, -70 * 16, 140 * 16)

    painter.end()
    return QIcon(pixmap)


def _create_microphone_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#cccccc"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawRoundedRect(4, 1, 8, 7, 3, 3)

    painter.drawLine(6, 3, 10, 3)
    painter.drawLine(6, 5, 10, 5)

    painter.drawLine(8, 8, 8, 13)

    painter.drawLine(4, 13, 12, 13)

    painter.end()
    return QIcon(pixmap)


def _create_config_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#cccccc"))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)

    painter.drawLine(2, 4, 14, 4)
    painter.drawLine(2, 8, 14, 8)
    painter.drawLine(2, 12, 14, 12)

    painter.end()
    return QIcon(pixmap)


def _create_settings_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#cccccc"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawEllipse(QPoint(8, 8), 4, 4)

    teeth_pen = QPen(QColor("#cccccc"))
    teeth_pen.setWidthF(2.2)
    teeth_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(teeth_pen)

    import math
    for i in range(8):
        angle = i * math.pi / 4
        inner = QPointF(8 + 4.5 * math.cos(angle), 8 + 4.5 * math.sin(angle))
        outer = QPointF(8 + 7 * math.cos(angle), 8 + 7 * math.sin(angle))
        painter.drawLine(inner, outer)

    painter.setPen(pen)
    painter.drawEllipse(QPoint(8, 8), 2, 2)

    painter.end()
    return QIcon(pixmap)


def _create_extensions_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#cccccc"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    painter.drawRect(3, 5, 7, 7)
    painter.drawRect(10, 7, 4, 3)
    painter.drawRect(1, 7, 2, 3)

    painter.end()
    return QIcon(pixmap)


def _create_add_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    painter.drawLine(4, 8, 12, 8)
    painter.drawLine(8, 4, 8, 12)

    painter.end()
    return QIcon(pixmap)


def _create_delete_icon():
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)

    painter.drawLine(3, 3, 13, 13)
    painter.drawLine(13, 3, 3, 13)

    painter.end()
    return QIcon(pixmap)


class EQAPOEditor(CustomWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.EQAPOEditor")
        self.setWindowTitle(tr("app_title"))

        self.config_path = None
        self.output_device_path = None
        self.input_device_path = None
        self.file_watcher = QFileSystemWatcher(self)
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(300)
        self.save_timer.timeout.connect(self._save_config)

        self.file_change_timer = QTimer()
        self.file_change_timer.setSingleShot(True)
        self.file_change_timer.setInterval(200)
        self.file_change_timer.timeout.connect(self._load_config_from_file)

        self._ignored_paths = set()
        self._clear_ignore_timer = QTimer()
        self._clear_ignore_timer.setSingleShot(True)
        self._clear_ignore_timer.timeout.connect(self._ignored_paths.clear)

        self._loading = False
        self.other_lines = []

        self.output_mode = '15频段'
        self.input_mode = '15频段'
        self.output_variable_freqs = EQTab.DEFAULT_VARIABLE_FREQS.copy()
        self.input_variable_freqs = EQTab.DEFAULT_VARIABLE_FREQS.copy()

        self.config_manager = config_manager
        self._current_auto_eq_device = None
        self._auto_eq_dialog = None
        self._auto_eq_raw_content = {}
        self._auto_eq_type = {}

        self.app_config_manager = app_config_manager
        self._selected_app_path = None
        self._auto_switch_enabled = self.config_manager.get_auto_switch_enabled()
        self._notification_enabled = self.config_manager.get_notification_enabled()
        self._resident_config_enabled = self.config_manager.get_resident_config_enabled()
        self._exclude_default_config = self.config_manager.get_exclude_default_config()
        self._spk_enabled = self.config_manager.get_spk_enabled()
        self._mic_enabled = self.config_manager.get_mic_enabled()
        self._config_write_mode = self.config_manager.get_config_write_mode()
        self._switching_config = False
        self._adding_app = False

        self.app_detector = AppDetector(self)
        self.app_detector.appSwitchedToConfigured.connect(self._on_app_switched_to_configured)
        self.app_detector.appChangedFromConfigured.connect(self._on_app_switched_from_configured)

        self.process_detector = get_detector()

        self.output_device_name = self.config_manager.get_output_device_name()
        self.input_device_name = self.config_manager.get_input_device_name()
        self.output_preamp = self.config_manager.get_output_preamp()
        self.input_preamp = self.config_manager.get_input_preamp()
        self.output_gain_map = self.config_manager.get_output_gain_map()
        self.input_gain_map = self.config_manager.get_input_gain_map()
        self.output_mode = self.config_manager.get_output_mode() or self.output_mode
        self.input_mode = self.config_manager.get_input_mode() or self.input_mode
        self.output_variable_freqs = self.config_manager.get_output_variable_freqs() or self.output_variable_freqs
        self.input_variable_freqs = self.config_manager.get_input_variable_freqs() or self.input_variable_freqs
        self.output_left_balance, self.output_right_balance = self.config_manager.get_output_channel_balance()
        self.input_left_balance, self.input_right_balance = self.config_manager.get_input_channel_balance()

        self.dark_mode = True
        QApplication.instance().installEventFilter(self)

        self._block_save = False
        
        self.tray_enabled = self.config_manager.get_tray_enabled()

        self.automatic_startup = AutomaticStartup()

        self._create_central_widget()

        self.winId()
        if sys.platform == 'win32':
            try:
                dwmapi = ctypes.windll.dwmapi
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1)
                dwmapi.DwmSetWindowAttribute(
                    int(self.winId()),
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
            except Exception as e:
                self.logger.warning(f"设置深色标题栏失败: {e}")

        self.file_watcher.fileChanged.connect(self._on_file_changed)

        self._refresh_audio_devices()
        
        self.output_tab.set_device_by_name(self.output_device_name)
        self.input_tab.set_device_by_name(self.input_device_name)
        if not self.output_device_name:
            self.output_tab.set_device_enabled(True)
        if not self.input_device_name:
            self.input_tab.set_device_enabled(True)
        self.output_tab.set_preamp_gain(self.output_preamp)
        self.input_tab.set_preamp_gain(self.input_preamp)
        self.output_tab.set_channel_balance(self.output_left_balance, self.output_right_balance)
        self.input_tab.set_channel_balance(self.input_left_balance, self.input_right_balance)
        
        if self.output_gain_map:
            self.output_tab.set_frequencies_from_gain_map(self.output_gain_map)
        else:
            self.output_tab.set_mode_and_freqs(self.output_mode, self.output_variable_freqs)
        
        if self.input_gain_map:
            self.input_tab.set_frequencies_from_gain_map(self.input_gain_map)
        else:
            self.input_tab.set_mode_and_freqs(self.input_mode, self.input_variable_freqs)
        
        output_monitor = self.config_manager.get_monitor_state("output")
        input_monitor = self.config_manager.get_monitor_state("input")
        self.output_tab.monitor_combo.setCurrentIndex(output_monitor)
        self.input_tab.monitor_combo.setCurrentIndex(input_monitor)

        self.default_backup_dir = APP_DIR / "default_backup"

        self._last_modified_times = {}

        saved_config_path = self.config_manager.get_last_config_path()
        if saved_config_path:
            saved_path = Path(saved_config_path)
            if saved_path.exists():
                self._set_config_path(saved_path)

        signal.signal(signal.SIGINT, self.signal_handler)

        self.center_on_screen()

        self._init_system_tray()

        self._restore_app_cards_from_config()

        if self._auto_switch_enabled:
            self._start_auto_switch()

        on_language_changed(self._retranslate_ui)

    def _init_system_tray(self):
        self.tray_icon = QSystemTrayIcon()
        icon_path = get_icon_path()
        if icon_path:
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.tray_icon.setToolTip(tr("app_title"))

        self.tray_menu = QMenu(self)
        self.tray_menu.setWindowFlags(
            self.tray_menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self.tray_menu.setAttribute(Qt.WA_TranslucentBackground)
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px 2px;
            }
        """)

        self.show_hide_action, self.show_hide_btn = self._create_tray_action(
            tr("tray_show"), self._toggle_window
        )
        self.tray_menu.addAction(self.show_hide_action)

        self.tray_menu.addAction(self._create_tray_separator())

        self.exit_action, self.exit_btn = self._create_tray_action(
            tr("tray_exit"), self._exit_application
        )
        self.tray_menu.addAction(self.exit_action)

        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _create_tray_action(self, text, callback):
        action = QWidgetAction(self.tray_menu)
        btn = QPushButton(text)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumWidth(120)
        btn.setStyleSheet("""
            QPushButton {
                text-align: center;
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 7px 28px;
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0078D4;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        btn.clicked.connect(callback)
        action.setDefaultWidget(btn)
        return action, btn

    def _create_tray_separator(self):
        action = QWidgetAction(self.tray_menu)
        line = QWidget()
        line.setFixedHeight(1)
        line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        line.setMinimumWidth(80)
        line.setStyleSheet("""
            background-color: #3a3a3a;
            margin: 2px 8px;
        """)
        action.setDefaultWidget(line)
        return action

    def _toggle_window(self):
        if self.isVisible():
            self.hide()
            self.show_hide_btn.setText(tr("tray_show"))
        else:
            self.show()
            self.show_hide_btn.setText(tr("tray_hide"))

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            menu_size = self.tray_menu.sizeHint()
            cursor_pos = QCursor.pos()

            screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
            screen_geo = screen.availableGeometry()

            if cursor_pos.x() < screen_geo.center().x():
                x = cursor_pos.x() - menu_size.width()
            else:
                x = cursor_pos.x()

            y = cursor_pos.y() - menu_size.height()

            if y < screen_geo.top():
                y = cursor_pos.y()

            if x < screen_geo.left():
                x = screen_geo.left()
            elif x + menu_size.width() > screen_geo.right():
                x = screen_geo.right() - menu_size.width()

            if y + menu_size.height() > screen_geo.bottom():
                y = screen_geo.bottom() - menu_size.height()

            self.tray_menu.popup(QPoint(x, y))

    def _toggle_startup(self, checked):
        if checked:
            success = self.automatic_startup.enable()
            if success:
                self.logger.info("开机自启已启用")
            else:
                self.logger.error("开机自启启用失败")
                if hasattr(self, 'startup_checkbox'):
                    self.startup_checkbox.blockSignals(True)
                    self.startup_checkbox.setChecked(False)
                    self.startup_checkbox.blockSignals(False)
        else:
            success = self.automatic_startup.disable()
            if success:
                self.logger.info("开机自启已禁用")
            else:
                self.logger.error("开机自启禁用失败")
                if hasattr(self, 'startup_checkbox'):
                    self.startup_checkbox.blockSignals(True)
                    self.startup_checkbox.setChecked(True)
                    self.startup_checkbox.blockSignals(False)

    def _on_startup_checkbox_toggled(self, checked):
        self._toggle_startup(checked)

    def _toggle_tray(self, checked):
        self.tray_enabled = checked
        self.config_manager.set_tray_enabled(checked)
        if hasattr(self, 'tray_checkbox'):
            self.tray_checkbox.blockSignals(True)
            self.tray_checkbox.setChecked(checked)
            self.tray_checkbox.blockSignals(False)
        self.logger.info(f"软件托盘已{'启用' if checked else '禁用'}")
        if not checked:
            self.show()
            if hasattr(self, 'show_hide_btn'):
                self.show_hide_btn.setText(tr("tray_hide"))

    def _on_tray_checkbox_toggled(self, checked):
        self._toggle_tray(checked)

    def _on_language_changed(self, index):
        lang_code = self.lang_combo.itemData(index)
        if lang_code == self.config_manager.get_language():
            return
        self.config_manager.set_language(lang_code)
        set_language(lang_code)
        
        self.logger.info(f"语言已切换为: {lang_code}")
        lang_names = {"zh_CN": tr("lang_zh_CN"), "zh_TW": tr("lang_zh_TW"), "en": tr("lang_en")}
        reply = QMessageBox.question(
            self, tr("dialog_lang_switch"),
            tr("msg_lang_changed", lang=lang_names.get(lang_code, lang_code)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self._restart_application()

    def _restart_application(self):
        self.logger.info("正在重启程序（窗口重建）...")
        self.config_manager.sync()

        try:
            self.output_tab._stop_monitor()
            self.input_tab._stop_monitor()
            if hasattr(self, 'app_detector'):
                self.app_detector.stop()
        except Exception:
            pass

        if hasattr(self, '_auto_eq_dialog') and self._auto_eq_dialog is not None:
            try:
                if hasattr(self._auto_eq_dialog, 'download_worker') and self._auto_eq_dialog.download_worker is not None:
                    self._auto_eq_dialog.download_worker.requestInterruption()
                    self._auto_eq_dialog.download_worker.wait(2000)
                if hasattr(self._auto_eq_dialog, 'scan_worker') and self._auto_eq_dialog.scan_worker is not None:
                    self._auto_eq_dialog.scan_worker.requestInterruption()
                    self._auto_eq_dialog.scan_worker.wait(2000)
            except Exception:
                pass

        try:
            QThreadPool.globalInstance().clear()
            QThreadPool.globalInstance().waitForDone(2000)
        except Exception:
            pass

        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

        QApplication.instance().removeEventFilter(self)

        old = self

        global _app_window
        new_window = EQAPOEditor()
        _app_window = new_window
        if not new_window.tray_enabled:
            new_window.show()

        old.tray_icon.hide()
        old.hide()
        old.deleteLater()

    def _exit_application(self):
        try:
            self.logger.info("正在关闭程序，停止所有监听...")
            self.output_tab._stop_monitor()
            self.input_tab._stop_monitor()

            if hasattr(self, 'app_detector'):
                self.app_detector.stop()

            self.output_device_name = self.output_tab.get_device_name()
            self.input_device_name = self.input_tab.get_device_name()
            self.output_preamp = self.output_tab.get_preamp_gain()
            self.input_preamp = self.input_tab.get_preamp_gain()
            self.output_mode = self.output_tab.current_mode
            self.input_mode = self.input_tab.current_mode
            self.output_variable_freqs = self.output_tab._variable_freqs
            self.input_variable_freqs = self.input_tab._variable_freqs
            freqs, gains = self.output_tab.get_filter_gains()
            self.output_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}
            freqs, gains = self.input_tab.get_filter_gains()
            self.input_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}

            self.config_manager.set_output_device_name(self.output_device_name)
            self.config_manager.set_output_preamp(self.output_preamp)
            self.config_manager.set_output_mode(self.output_mode)
            self.config_manager.set_output_variable_freqs(self.output_variable_freqs)
            self.config_manager.set_output_gain_map(self.output_gain_map)
            self.config_manager.set_input_device_name(self.input_device_name)
            self.config_manager.set_input_preamp(self.input_preamp)
            self.config_manager.set_input_mode(self.input_mode)
            self.config_manager.set_input_variable_freqs(self.input_variable_freqs)
            self.config_manager.set_input_gain_map(self.input_gain_map)
            self.config_manager.sync()

            if hasattr(self, '_auto_eq_dialog') and self._auto_eq_dialog is not None:
                if hasattr(self._auto_eq_dialog, 'download_worker') and self._auto_eq_dialog.download_worker is not None:
                    self._auto_eq_dialog.download_worker.requestInterruption()
                    self._auto_eq_dialog.download_worker.wait(2000)
                if hasattr(self._auto_eq_dialog, 'scan_worker') and self._auto_eq_dialog.scan_worker is not None:
                    self._auto_eq_dialog.scan_worker.requestInterruption()
                    self._auto_eq_dialog.scan_worker.wait(2000)

            QThreadPool.globalInstance().clear()
            QThreadPool.globalInstance().waitForDone(2000)

            try:
                import sounddevice as sd
                sd.stop()
            except:
                pass

        except Exception as e:
            self.logger.exception("关闭时发生异常")
        finally:
            QApplication.instance().removeEventFilter(self)
            QApplication.quit()



    def signal_handler(self, signum, frame):
        self.logger.info("收到中断信号，正在退出...")
        QApplication.quit()

    @staticmethod
    def _enable_dark_title_bar(hwnd, enable):
        if sys.platform != 'win32':
            return
        try:
            dwmapi = ctypes.windll.dwmapi
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1 if enable else 0)
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        except Exception as e:
            pass

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QWidget):
            if self.dark_mode and obj.windowHandle():
                hwnd = int(obj.winId())
                self._enable_dark_title_bar(hwnd, True)
        return super().eventFilter(obj, event)

    def _set_hint_text(self, text):
        widget = self._hint_app_label
        layout = widget.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        add_pixmap = _create_add_icon().pixmap(16, 16)

        icon_map = {
            "{add_icon}": add_pixmap,
        }

        lines = text.split("\n")
        for line in lines:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            parts = re.split(r"(\{add_icon\})", line)
            for part in parts:
                if part in icon_map:
                    icon_label = QLabel()
                    icon_label.setPixmap(icon_map[part].scaled(
                        14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
                    icon_label.setFixedSize(14, 14)
                    row_layout.addWidget(icon_label)
                elif part:
                    label = QLabel(part)
                    label.setStyleSheet("color: #666666; font-size: 9pt;")
                    row_layout.addWidget(label)

            row_layout.addStretch()
            layout.addWidget(row)

    def _retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        self.tray_icon.setToolTip(tr("app_title"))

        self.show_hide_btn.setText(tr("tray_show") if self.isVisible() else tr("tray_hide"))
        self.exit_btn.setText(tr("tray_exit"))

        self.tab_widget.setTabText(0, tr("tab_speaker"))
        self.tab_widget.setTabText(1, tr("tab_microphone"))
        self.tab_widget.setTabText(2, tr("tab_config"))
        self.tab_widget.setTabText(3, tr("tab_extensions"))
        self.tab_widget.setTabText(4, tr("tab_settings"))

        if hasattr(self, '_title_cfg'):
            self._title_cfg.setText(tr("card_config_management"))
        if hasattr(self, '_title_tools'):
            self._title_tools.setText(tr("card_reset_maintenance"))
        if hasattr(self, '_title_app'):
            self._title_app.setText(tr("card_app_behavior"))
        if hasattr(self, '_title_lang'):
            self._title_lang.setText(tr("card_language"))
        if hasattr(self, 'select_folder_btn'):
            self.select_folder_btn.setText(tr("btn_select_config_folder"))
        if hasattr(self, 'folder_path_label'):
            self.folder_path_label.setToolTip(tr("tooltip_current_config_path"))
            self.folder_path_label.setPlaceholderText(tr("placeholder_paste_path"))
        if hasattr(self, 'install_btn'):
            self.install_btn.setText(tr("btn_install"))
        if hasattr(self, 'uninstall_btn'):
            self.uninstall_btn.setText(tr("btn_uninstall"))
        if hasattr(self, 'reset_btn'):
            self.reset_btn.setText(tr("btn_reset_settings"))
        if hasattr(self, 'clear_logs_btn'):
            self.clear_logs_btn.setText(tr("btn_clear_logs"))
        if hasattr(self, 'open_log_folder_btn'):
            self.open_log_folder_btn.setText(tr("btn_open_logs"))

        if hasattr(self, 'tray_checkbox'):
            self.tray_checkbox.setText(tr("toggle_tray"))
        if hasattr(self, 'startup_checkbox'):
            self.startup_checkbox.setText(tr("toggle_startup"))
        if hasattr(self, 'auto_switch_switch'):
            self.auto_switch_switch.setText(tr("toggle_auto_switch"))
        if hasattr(self, 'resident_config_switch'):
            self.resident_config_switch.setText(tr("toggle_resident_config"))
        if hasattr(self, 'exclude_default_switch'):
            self.exclude_default_switch.setText(tr("toggle_exclude_default_config"))
        if hasattr(self, 'notification_switch'):
            self.notification_switch.setText(tr("toggle_notification"))
        if hasattr(self, 'spk_switch'):
            self.spk_switch.setText(tr("toggle_spk_file"))
        if hasattr(self, 'mic_switch'):
            self.mic_switch.setText(tr("toggle_mic_file"))
        if hasattr(self, 'config_write_mode_combo'):
            self.config_write_mode_combo.setItemText(0, tr("combo_config_write_mode"))
            self.config_write_mode_combo.setItemText(1, tr("combo_config_preserve_mode"))

        if hasattr(self, 'lang_combo'):
            self.lang_combo.setItemText(0, tr("lang_zh_CN"))
            self.lang_combo.setItemText(1, tr("lang_zh_TW"))
            self.lang_combo.setItemText(2, tr("lang_en"))
        if hasattr(self, 'lang_label'):
            self.lang_label.setText(tr("label_interface_language"))
        if hasattr(self, '_header_apps_label'):
            self._header_apps_label.setText(tr("header_apps"))
        if hasattr(self, '_hint_app_label'):
            self._set_hint_text(tr("hint_app_management"))

    def closeEvent(self, event):
        self.output_device_name = self.output_tab.get_device_name()
        self.input_device_name = self.input_tab.get_device_name()
        self.output_preamp = self.output_tab.get_preamp_gain()
        self.input_preamp = self.input_tab.get_preamp_gain()
        self.output_mode = self.output_tab.current_mode
        self.input_mode = self.input_tab.current_mode
        self.output_variable_freqs = self.output_tab._variable_freqs
        self.input_variable_freqs = self.input_tab._variable_freqs
        freqs, gains = self.output_tab.get_filter_gains()
        self.output_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}
        freqs, gains = self.input_tab.get_filter_gains()
        self.input_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}

        self.config_manager.set_output_device_name(self.output_device_name)
        self.config_manager.set_output_preamp(self.output_preamp)
        self.config_manager.set_output_mode(self.output_mode)
        self.config_manager.set_output_variable_freqs(self.output_variable_freqs)
        self.config_manager.set_output_gain_map(self.output_gain_map)
        self.config_manager.set_input_device_name(self.input_device_name)
        self.config_manager.set_input_preamp(self.input_preamp)
        self.config_manager.set_input_mode(self.input_mode)
        self.config_manager.set_input_variable_freqs(self.input_variable_freqs)
        self.config_manager.set_input_gain_map(self.input_gain_map)
        self.config_manager.sync()

        if self.tray_enabled:
            self.logger.info("最小化到托盘")
            self.hide()
            self.show_hide_btn.setText(tr("tray_show"))
            event.ignore()
            return
        
        try:
            self.logger.info("正在关闭程序，停止所有监听...")
            self.output_tab._stop_monitor()
            self.input_tab._stop_monitor()

            if hasattr(self, 'app_detector'):
                self.app_detector.stop()

            if hasattr(self, '_auto_eq_dialog') and self._auto_eq_dialog is not None:
                if hasattr(self._auto_eq_dialog,
                           'download_worker') and self._auto_eq_dialog.download_worker is not None:
                    self._auto_eq_dialog.download_worker.requestInterruption()
                    self._auto_eq_dialog.download_worker.wait(2000)
                if hasattr(self._auto_eq_dialog, 'scan_worker') and self._auto_eq_dialog.scan_worker is not None:
                    self._auto_eq_dialog.scan_worker.requestInterruption()
                    self._auto_eq_dialog.scan_worker.wait(2000)

            QThreadPool.globalInstance().clear()
            QThreadPool.globalInstance().waitForDone(2000)

            try:
                import sounddevice as sd
                sd.stop()
            except:
                pass

        except Exception as e:
            self.logger.exception("关闭时发生异常")
        finally:
            QApplication.instance().removeEventFilter(self)
            event.accept()
            super().closeEvent(event)

    def get_output_audio_device(self):
        return self.output_tab.get_audio_device()

    def get_input_audio_device(self):
        return self.input_tab.get_audio_device()

    def _create_settings_card(self, title):
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 14, 20, 18)
        card_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("settingsCardTitle")
        card_layout.addWidget(title_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #3e3e3e;")
        card_layout.addWidget(separator)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 4, 0, 0)
        content_layout.setSpacing(8)
        card_layout.addWidget(content_widget)

        return card, content_layout, title_label

    def _create_config_tab(self):
        outer_layout = QVBoxLayout(self.config_tab)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 4, 0, 4)
        top_bar.setSpacing(12)

        title_label = QLabel(tr("header_apps"))
        self._header_apps_label = title_label
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 10pt;
                font-weight: bold;
                padding: 0px;
            }
        """)
        top_bar.addWidget(title_label)

        self.add_app_btn = QPushButton()
        self.add_app_btn.setObjectName("addAppButton")
        self.add_app_btn.setIcon(_create_add_icon())
        self.add_app_btn.setIconSize(QSize(14, 14))
        self.add_app_btn.setFixedSize(42, 24)
        self.add_app_btn.setStyleSheet("""
            QPushButton#addAppButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 4px;
            }
            QPushButton#addAppButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton#addAppButton:pressed {
                background-color: #5a5a5a;
            }
        """)
        self.add_app_btn.clicked.connect(self._add_game_app)
        top_bar.addWidget(self.add_app_btn)

        self.auto_switch_switch = ToggleSwitch(tr("toggle_auto_switch"))
        self.auto_switch_switch.setChecked(self._auto_switch_enabled)
        self.auto_switch_switch.toggled.connect(self._on_auto_switch_toggled)
        top_bar.addWidget(self.auto_switch_switch)

        self.app_cards = {}

        self.resident_config_switch = ToggleSwitch(tr("toggle_resident_config"))
        self.resident_config_switch.setChecked(self._resident_config_enabled)
        self.resident_config_switch.toggled.connect(self._on_resident_config_toggled)
        top_bar.addWidget(self.resident_config_switch)

        self.exclude_default_switch = ToggleSwitch(tr("toggle_exclude_default_config"))
        self.exclude_default_switch.setChecked(self._exclude_default_config)
        self.exclude_default_switch.toggled.connect(self._on_exclude_default_config_toggled)
        top_bar.addWidget(self.exclude_default_switch)

        self.notification_switch = ToggleSwitch(tr("toggle_notification"))
        self.notification_switch.setChecked(self._notification_enabled)
        self.notification_switch.toggled.connect(self._on_notification_toggled)
        top_bar.addWidget(self.notification_switch)

        top_bar.addStretch()
        outer_layout.addLayout(top_bar)

        hint_widget = QWidget()
        self._hint_app_label = hint_widget
        hint_layout = QVBoxLayout(hint_widget)
        hint_layout.setContentsMargins(12, 2, 12, 2)
        hint_layout.setSpacing(2)
        outer_layout.addWidget(hint_widget)
        self._set_hint_text(tr("hint_app_management"))

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(12, 0, 0, 0)
        main_layout.setSpacing(0)

        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 24, 24)
        content_layout.setSpacing(16)

        outer_layout.addLayout(main_layout)

        apps_scroll = QScrollArea()
        apps_scroll.setWidgetResizable(True)
        apps_scroll.setFrameShape(QFrame.NoFrame)
        apps_scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        apps_content = QWidget()
        self.apps_layout = QHBoxLayout(apps_content)
        self.apps_layout.setContentsMargins(0, 0, 0, 0)
        self.apps_layout.setSpacing(12)

        self.apps_layout.addStretch()
        apps_scroll.setWidget(apps_content)
        content_layout.addWidget(apps_scroll)

        main_layout.addWidget(content_area)

        self.config_layout = content_layout

    def _create_app_card(self, app_name, app_path):
        card = QFrame()
        card.setObjectName("configAppCard")
        card.setStyleSheet("""
            QFrame#configAppCard {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
                min-width: 220px;
                max-width: 220px;
                max-height: 283px;
            }
            QFrame#configAppCard[selected="true"] {
                border: 2px solid #0078D4;
                background-color: #2a3040;
            }
        """)
        card.setCursor(Qt.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setScaledContents(True)
        icon_label.setAlignment(Qt.AlignCenter)

        app_icon = self._get_app_icon_from_exe(app_path)
        if app_icon:
            icon_label.setPixmap(app_icon.pixmap(48, 48))
        else:
            icon_label.setText(self._get_default_app_icon(app_name))

        card_layout.addWidget(icon_label, alignment=Qt.AlignCenter)

        title_label = QLabel(app_name)
        title_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #ffffff;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        config_status = QWidget()
        config_status.setObjectName("configStatusWidget")
        status_layout = QVBoxLayout(config_status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(2)
        status_layout.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(config_status)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        delete_btn = QPushButton()
        delete_btn.setIcon(_create_delete_icon())
        delete_btn.setIconSize(QSize(14, 14))
        delete_btn.setFixedSize(28, 28)
        delete_btn.setToolTip(tr("tooltip_delete_app"))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a2a2a;   /* 深红色底 */
                border: 1px solid #6a4a4a;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #5a3a3a; }
        """)
        delete_btn.clicked.connect(lambda: self._remove_app_card(card, app_path))
        btn_layout.addWidget(delete_btn, alignment=Qt.AlignCenter)

        card_layout.addLayout(btn_layout)

        card.mousePressEvent = lambda event, p=app_path, c=card: self._select_app_card(p, c)

        status = card.findChild(QWidget, "configStatusWidget")
        if status:
            self._populate_config_status(status, app_path)

        return card

    def _get_config_status_info(self, app_path):
        has_config = self.app_config_manager.has_config(app_path)
        out_dev = None
        in_dev = None
        if has_config:
            config = self.app_config_manager.get_app_config(app_path)
            if config:
                out_cfg = config.get("output", {})
                in_cfg = config.get("input", {})
                out_dev = out_cfg.get("device_name")
                in_dev = in_cfg.get("device_name")
        return has_config, out_dev, in_dev

    def _populate_config_status(self, widget, app_path):
        layout = widget.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_config, out_dev, in_dev = self._get_config_status_info(app_path)

        if not has_config:
            label = QLabel(tr("config_status_not_configured"))
            label.setStyleSheet("font-size: 7pt; color: #666666;")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return

        color = "#6bff6b"
        spk_icon = _create_speaker_icon()
        mic_icon = _create_microphone_icon()

        if out_dev:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            row_layout.setAlignment(Qt.AlignCenter)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(spk_icon.pixmap(14, 14))
            icon_lbl.setFixedSize(14, 14)
            row_layout.addWidget(icon_lbl)
            text_lbl = QLabel(tr("config_status_configured"))
            text_lbl.setStyleSheet(f"font-size: 7pt; color: {color};")
            row_layout.addWidget(text_lbl)
            layout.addWidget(row)

        if in_dev:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            row_layout.setAlignment(Qt.AlignCenter)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(mic_icon.pixmap(14, 14))
            icon_lbl.setFixedSize(14, 14)
            row_layout.addWidget(icon_lbl)
            text_lbl = QLabel(tr("config_status_configured"))
            text_lbl.setStyleSheet(f"font-size: 7pt; color: {color};")
            row_layout.addWidget(text_lbl)
            layout.addWidget(row)

        if not out_dev and not in_dev:
            label = QLabel(tr("config_status_configured"))
            label.setStyleSheet(f"font-size: 7pt; color: {color};")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)

    _shared_icon_provider = None

    @classmethod
    def _get_shared_icon_provider(cls):
        if cls._shared_icon_provider is None:
            from PySide6.QtWidgets import QFileIconProvider
            cls._shared_icon_provider = QFileIconProvider()
        return cls._shared_icon_provider

    def _get_app_icon_from_exe(self, exe_path):
        try:
            from PySide6.QtCore import QFileInfo
            
            file_info = QFileInfo(exe_path)
            icon = self._get_shared_icon_provider().icon(file_info)
            
            if not icon.isNull():
                return icon
                
        except Exception as e:
            self.logger.debug(f"无法从 {exe_path} 提取图标: {e}")
        
        return None

    def _get_default_app_icon(self, app_name):
        icons = {
            "steam": "♜",
            "game": "⚂",
            "chrome": "⬢",
            "edge": "◆",
            "firefox": "✦",
            "discord": "✉",
            "teams": "⚒",
            "zoom": "◉",
            "spotify": "♪",
            "music": "♫",
            "video": "▶",
            "player": "▶",
            "explorer": "☰",
            "terminal": "⚡",
        }
        app_name_lower = app_name.lower()
        for key, icon in icons.items():
            if key in app_name_lower:
                return icon
        return "◻"

    def _add_game_app(self):
        self._adding_app = True
        self._stop_exclude_retry()
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("dialog_select_app"),
                str(Path.home().anchor),
                tr("file_filter_exe")
            )
        finally:
            self._adding_app = False
        if file_path:
            app_path = str(Path(file_path).resolve())
            app_name = Path(file_path).stem

            existing = self.app_config_manager.get_all_apps()
            for app in existing:
                if app["app_path"] == app_path:
                    QMessageBox.information(self, tr("dialog_info"), f"应用 '{app['app_name']}' 已存在")
                    return

            if self.apps_layout.count() > 0:
                item = self.apps_layout.takeAt(self.apps_layout.count() - 1)
                if item:
                    del item

            self.app_config_manager.save_app_config(app_path, app_name, {
                "output": self._capture_config_from_tabs("output"),
                "input": self._capture_config_from_tabs("input")
            })

            card = self._create_app_card(app_name, app_path)
            self.app_cards[app_path] = card
            self.apps_layout.addWidget(card)
            self.apps_layout.addStretch()

            self.app_detector.add_configured_app(app_path)

            rule = self.process_detector.get_app_rule(app_path)
            if rule and rule.auto_discovered_aliases:
                detected_aliases = list(rule.auto_discovered_aliases)
                self.app_config_manager.set_app_aliases(app_path, app_name, detected_aliases)
                self.logger.info(f"已自动发现 {app_name} 的别名: {detected_aliases}")

            self._select_app_card(app_path, card)
            self.logger.info(f"已添加应用: {app_name} ({app_path})")

    def _create_resident_card(self):
        if RESIDENT_KEY in self.app_cards:
            return

        if self.apps_layout.count() > 0:
            item = self.apps_layout.takeAt(self.apps_layout.count() - 1)
            if item:
                del item

        self.app_config_manager.save_app_config(RESIDENT_KEY, "EQAPO编辑器", {
            "output": self._capture_config_from_tabs("output"),
            "input": self._capture_config_from_tabs("input")
        })

        card = self._create_resident_app_card()
        self.app_cards[RESIDENT_KEY] = card
        self.apps_layout.insertWidget(0, card)
        self.apps_layout.addStretch()

        self._update_card_selection_only(RESIDENT_KEY, card)

        self.logger.info("已创建 EQAPO 编辑器专属配置卡片")

    def _remove_resident_card(self):
        if RESIDENT_KEY not in self.app_cards:
            return

        card = self.app_cards[RESIDENT_KEY]
        index = self.apps_layout.indexOf(card)
        if index != -1:
            self.apps_layout.removeWidget(card)
            card.deleteLater()
        del self.app_cards[RESIDENT_KEY]
        self.app_config_manager.delete_app_config(RESIDENT_KEY)

        if self._selected_app_path == RESIDENT_KEY:
            self._selected_app_path = None
            self._clear_card_selection()

        self.logger.info("已移除 EQAPO 编辑器专属配置卡片")

    def _create_resident_app_card(self):
        card = QFrame()
        card.setObjectName("configAppCard")
        card.setStyleSheet("""
            QFrame#configAppCard {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
                min-width: 220px;
                max-width: 220px;
                max-height: 283px;
            }
            QFrame#configAppCard[selected="true"] {
                border: 2px solid #0078D4;
                background-color: #2a3040;
            }
        """)
        card.setCursor(Qt.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setScaledContents(True)
        icon_label.setAlignment(Qt.AlignCenter)

        icon_path = get_icon_path()
        if icon_path:
            icon_label.setPixmap(QIcon(str(icon_path)).pixmap(48, 48))
        else:
            icon_label.setText("🎛")

        card_layout.addWidget(icon_label, alignment=Qt.AlignCenter)

        title_label = QLabel(tr("app_title"))
        title_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #ffffff;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        config_status = QWidget()
        config_status.setObjectName("configStatusWidget")
        status_layout = QVBoxLayout(config_status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(2)
        status_layout.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(config_status)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        delete_btn = QPushButton()
        delete_btn.setIcon(_create_delete_icon())
        delete_btn.setIconSize(QSize(14, 14))
        delete_btn.setFixedSize(28, 28)
        delete_btn.setToolTip(tr("tooltip_delete_app"))
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a2a2a;
                border: 1px solid #6a4a4a;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #5a3a3a; }
        """)
        delete_btn.clicked.connect(self._delete_resident_card)
        btn_layout.addWidget(delete_btn, alignment=Qt.AlignCenter)

        card_layout.addLayout(btn_layout)

        card.mousePressEvent = lambda event, c=card: self._select_app_card(RESIDENT_KEY, c)

        status = card.findChild(QWidget, "configStatusWidget")
        if status:
            self._populate_config_status(status, RESIDENT_KEY)

        return card

    def _delete_resident_card(self):
        if hasattr(self, 'resident_config_switch'):
            self.resident_config_switch.setChecked(False)
        self._on_resident_config_toggled(False)

    def _save_config_to_resident(self):
        self.app_config_manager.save_app_config(
            RESIDENT_KEY,
            "EQAPO编辑器",
            {
                "output": self._capture_config_from_tabs("output"),
                "input": self._capture_config_from_tabs("input")
            }
        )
        if RESIDENT_KEY in self.app_cards:
            card = self.app_cards[RESIDENT_KEY]
            status = card.findChild(QWidget, "configStatusWidget")
            if status:
                self._populate_config_status(status, RESIDENT_KEY)
        self.logger.info("已保存 EQAPO 编辑器专属配置")

    def _remove_app_card(self, card, app_path):
        normalized = str(Path(app_path).resolve())
        index = self.apps_layout.indexOf(card)
        if index != -1:
            self.apps_layout.removeWidget(card)
            card.deleteLater()
            if normalized in self.app_cards:
                del self.app_cards[normalized]
            self.app_config_manager.delete_app_config(normalized)
            self.app_detector.remove_configured_app(normalized)
            self.process_detector.remove_app_rule(normalized)
            if self._selected_app_path == normalized:
                self._selected_app_path = None
                self._clear_card_selection()
            self.logger.info(f"已删除应用配置: {normalized}")

    def _on_auto_switch_toggled(self, checked):
        self._auto_switch_enabled = checked
        self.config_manager.set_auto_switch_enabled(checked)
        if checked:
            self._start_auto_switch()
        else:
            self._stop_auto_switch()

    def _on_exclude_default_config_toggled(self, checked):
        self._exclude_default_config = checked
        self.config_manager.set_exclude_default_config(checked)

    def _on_notification_toggled(self, checked):
        self._notification_enabled = checked
        self.config_manager.set_notification_enabled(checked)

    def _on_spk_toggled(self, checked):
        self._spk_enabled = checked
        self.config_manager.set_spk_enabled(checked)
        self._on_any_value_changed()

    def _on_mic_toggled(self, checked):
        self._mic_enabled = checked
        self.config_manager.set_mic_enabled(checked)
        self._on_any_value_changed()

    def _on_config_write_mode_changed(self, index):
        self._config_write_mode = self.config_write_mode_combo.itemData(index)
        self.config_manager.set_config_write_mode(self._config_write_mode)

    def _show_notification(self, title, message, duration=5000, app_icon=None):
        if self._notification_enabled:
            NotificationPopup.show_notification(title, message, duration, self, app_icon)

    def _on_resident_config_toggled(self, checked):
        self._resident_config_enabled = checked
        self.config_manager.set_resident_config_enabled(checked)
        if checked:
            self._create_resident_card()
            self._save_config_to_resident()
        else:
            self._selected_app_path = None
            self._clear_card_selection()
            self._remove_resident_card()
            if self.app_cards:
                first_path = next(iter(self.app_cards))
                first_card = self.app_cards[first_path]
                self._select_app_card(first_path, first_card)

    def _select_app_card(self, app_path, card):
        if app_path == RESIDENT_KEY:
            normalized = RESIDENT_KEY
        else:
            normalized = str(Path(app_path).resolve())
        self._clear_card_selection()

        card.setProperty("selected", "true")
        card.style().unpolish(card)
        card.style().polish(card)

        self._selected_app_path = normalized
        self.config_manager.set_last_active_app(normalized)

        app_config = self.app_config_manager.get_app_config(normalized)
        self._loading = True
        try:
            if app_config:
                self._load_app_config_to_tabs(app_config)
                app_name = app_config.get("app_name", "EQAPO编辑器" if normalized == RESIDENT_KEY else Path(normalized).stem)
            else:
                app_name = "EQAPO编辑器" if normalized == RESIDENT_KEY else Path(normalized).stem
        finally:
            self._loading = False

        self._on_any_value_changed()

    def _clear_card_selection(self):
        for path, card in self.app_cards.items():
            card.setProperty("selected", "false")
            card.style().unpolish(card)
            card.style().polish(card)

    def _update_card_selection_only(self, app_path, card):
        self._clear_card_selection()
        card.setProperty("selected", "true")
        card.style().unpolish(card)
        card.style().polish(card)
        if app_path == RESIDENT_KEY:
            self._selected_app_path = RESIDENT_KEY
        else:
            self._selected_app_path = str(Path(app_path).resolve())

    def _save_config_to_app(self, app_path):
        if app_path == RESIDENT_KEY:
            normalized = RESIDENT_KEY
        else:
            normalized = str(Path(app_path).resolve())
        app_config = self.app_config_manager.get_app_config(normalized)
        if app_config and app_config.get("app_name"):
            app_name = app_config["app_name"]
        elif normalized == RESIDENT_KEY:
            app_name = "EQAPO编辑器"
        else:
            app_name = Path(normalized).stem

        self.app_config_manager.save_app_config(
            normalized,
            app_name,
            {
                "output": self._capture_config_from_tabs("output"),
                "input": self._capture_config_from_tabs("input")
            }
        )

        if normalized in self.app_cards:
            card = self.app_cards[normalized]
            status = card.findChild(QWidget, "configStatusWidget")
            if status:
                self._populate_config_status(status, normalized)

        self.logger.info(f"已保存配置到: {app_name}")

    def _restore_app_cards_from_config(self):
        apps = self.app_config_manager.get_all_apps()

        while self.apps_layout.count() > 0:
            item = self.apps_layout.takeAt(0)
            if item:
                del item

        for app in apps:
            app_path = app["app_path"]
            if app_path == RESIDENT_KEY:
                card = self._create_resident_app_card()
                self.app_cards[app_path] = card
                self.apps_layout.insertWidget(0, card)
                break

        for app in apps:
            app_path = app["app_path"]
            if app_path == RESIDENT_KEY:
                continue
            if Path(app_path).exists():
                card = self._create_app_card(app["app_name"], app_path)
                self.app_cards[app_path] = card
                self.apps_layout.addWidget(card)
                self.app_detector.add_configured_app(app_path)

                detection = app.get("config", {}).get("detection", {})
                if detection:
                    aliases = detection.get("aliases", [])
                    if aliases:
                        self.process_detector.add_aliases(app_path, aliases)
                    if detection.get("wildcard_patterns"):
                        rule = self.process_detector.get_app_rule(app_path)
                        if rule:
                            rule.wildcard_patterns = detection["wildcard_patterns"]
                    if detection.get("regex_patterns"):
                        rule = self.process_detector.get_app_rule(app_path)
                        if rule:
                            rule.regex_patterns = detection["regex_patterns"]
                    if detection.get("command_keywords"):
                        rule = self.process_detector.get_app_rule(app_path)
                        if rule:
                            rule.command_keywords = detection["command_keywords"]

        self.apps_layout.addStretch()

        if self._resident_config_enabled and RESIDENT_KEY not in self.app_cards:
            self._create_resident_card()

        if self._resident_config_enabled and RESIDENT_KEY in self.app_cards:
            self._update_card_selection_only(RESIDENT_KEY, self.app_cards[RESIDENT_KEY])
            app_config = self.app_config_manager.get_app_config(RESIDENT_KEY)
            if app_config:
                self._loading = True
                try:
                    self._load_app_config_to_tabs(app_config)
                finally:
                    self._loading = False
        else:
            last_active = self.config_manager.get_last_active_app()
            if last_active and last_active in self.app_cards:
                self._update_card_selection_only(last_active, self.app_cards[last_active])
                app_config = self.app_config_manager.get_app_config(last_active)
                if app_config:
                    self._loading = True
                    try:
                        self._load_app_config_to_tabs(app_config)
                    finally:
                        self._loading = False

    def _start_auto_switch(self):
        configured_paths = [p for p in self.app_cards.keys() if p != RESIDENT_KEY]
        self.app_detector.set_configured_apps(configured_paths)
        self.app_detector.start()
        self.logger.info("自动切换已启动")

    def _stop_auto_switch(self):
        self.app_detector.stop()
        self.logger.info("自动切换已停止")

    def _on_app_switched_to_configured(self, app_path):
        if self._switching_config:
            return
        self._last_configured_pid = self.app_detector.current_pid
        self._stop_exclude_retry()
        self._switch_to_app_config(app_path)

    def _on_app_switched_from_configured(self, app_path):
        if self._switching_config or self._adding_app:
            return
        if self._exclude_default_config and self._resident_config_enabled:
            self._schedule_exclude_retry()
            return
        if self._resident_config_enabled and RESIDENT_KEY in self.app_cards:
            self._switch_to_resident_config()

    def _is_app_process_running(self, pid=None, app_path=None):
        pid = pid or getattr(self, '_last_configured_pid', None)
        app_path = app_path or self._selected_app_path
        if not app_path or app_path == RESIDENT_KEY:
            return False

        try:
            import psutil
            if pid and self._check_specific_pid(pid):
                return True

            target_name = Path(app_path).name.lower()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if not (proc.info['name'] and proc.info['name'].lower() == target_name):
                        continue
                    try:
                        exe = proc.exe()
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        self._last_configured_pid = proc.info['pid']
                        return True
                    except psutil.NoSuchProcess:
                        continue
                    proc_info = ProcessInfo(
                        pid=proc.info['pid'],
                        name=proc.info['name'],
                        exe_path=exe,
                    )
                    if self.process_detector.match_process_to_any_rule(proc_info):
                        self._last_configured_pid = proc.info['pid']
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.logger.debug(f"_is_app_process_running 异常: {e}")
        return False

    def _check_specific_pid(self, pid):
        import psutil
        try:
            if not psutil.pid_exists(pid):
                return False
            proc = psutil.Process(pid)
            try:
                exe = proc.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                return True
            except psutil.NoSuchProcess:
                return False
            name = ''
            try:
                name = proc.name() or ''
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            proc_info = ProcessInfo(pid=pid, name=name, exe_path=exe)
            return bool(self.process_detector.match_process_to_any_rule(proc_info))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            self.logger.debug(f"_check_specific_pid 异常: {e}")
            return False

    def _is_any_configured_app_running(self):
        import psutil
        if not self.app_cards:
            return False

        app_paths = [p for p in self.app_cards if p != RESIDENT_KEY]
        if not app_paths:
            return False

        target_names = {}
        for app_path in app_paths:
            name = Path(app_path).name.lower()
            if name not in target_names:
                target_names[name] = []
            target_names[name].append(app_path)

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name']
                if not proc_name:
                    continue
                proc_name_lower = proc_name.lower()
                if proc_name_lower not in target_names:
                    continue
                try:
                    exe = proc.exe()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    return True
                except psutil.NoSuchProcess:
                    continue
                proc_info = ProcessInfo(
                    pid=proc.info['pid'],
                    name=proc_name,
                    exe_path=exe,
                )
                if self.process_detector.match_process_to_any_rule(proc_info):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _schedule_exclude_retry(self):
        self._exclude_retry_app_path = self._selected_app_path
        self._exclude_retry_pid = self._last_configured_pid
        self._exclude_retry_count = 0
        if not hasattr(self, '_exclude_retry_timer'):
            self._exclude_retry_timer = QTimer(self)
            self._exclude_retry_timer.setSingleShot(True)
            self._exclude_retry_timer.timeout.connect(self._retry_exclude_switch)
        self._exclude_retry_timer.start(3000)

    def _stop_exclude_retry(self):
        if hasattr(self, '_exclude_retry_timer') and self._exclude_retry_timer.isActive():
            self._exclude_retry_timer.stop()

    def _retry_exclude_switch(self):
        if self._switching_config or self._adding_app:
            return
        retry_app = getattr(self, '_exclude_retry_app_path', None)
        if retry_app is not None and self._selected_app_path != retry_app:
            return
        if self._is_any_configured_app_running():
            return
        count = getattr(self, '_exclude_retry_count', 0) + 1
        if count < 4:
            self._exclude_retry_count = count
            self._exclude_retry_timer.start(3000)
            return
        if self._resident_config_enabled and RESIDENT_KEY in self.app_cards:
            self._switch_to_resident_config()


    def _switch_to_app_config(self, app_path):
        if self._switching_config:
            return

        if app_path == RESIDENT_KEY:
            normalized = RESIDENT_KEY
        else:
            normalized = str(Path(app_path).resolve()).lower()
        if self._selected_app_path and (self._selected_app_path.lower() == normalized or str(Path(self._selected_app_path).resolve()).lower() == normalized):
            return

        self.save_timer.stop()
        self._switching_config = True
        try:
            app_config = self.app_config_manager.get_app_config(app_path)
            if app_config is None:
                self._switching_config = False
                return

            app_name = app_config.get("app_name", Path(app_path).stem)
            self.logger.info(f"自动切换配置到: {app_name}")

            self.config_manager.set_last_active_app(app_path)

            if app_path in self.app_cards:
                self._update_card_selection_only(app_path, self.app_cards[app_path])

            if self._notification_enabled:
                app_icon = self._get_app_icon_from_exe(app_path)
                self._show_notification(
                    tr("msg_config_switched"),
                    app_name,
                    app_icon=app_icon
                )

            self._loading = True
            QTimer.singleShot(0, lambda: self._deferred_load_tab_config(app_config))

        except Exception:
            self._switching_config = False
            raise

    def _deferred_load_tab_config(self, app_config):
        t0 = time.perf_counter()
        try:
            self._load_app_config_to_tabs(app_config)
        finally:
            self._loading = False
            self._switching_config = False
            t1 = time.perf_counter()
            self.logger.debug(f"[CPU探针] _deferred_load_tab_config: {(t1-t0)*1000:.1f}ms")
            if hasattr(self, '_save_config'):
                self._on_any_value_changed()

    def _switch_to_resident_config(self):
        if self._switching_config:
            return
        if self._selected_app_path == RESIDENT_KEY:
            return

        self.save_timer.stop()
        self._switching_config = True
        try:
            app_config = self.app_config_manager.get_app_config(RESIDENT_KEY)
            if app_config is None:
                self._switching_config = False
                return

            self.logger.info("回退到常驻配置")

            if RESIDENT_KEY in self.app_cards:
                self._update_card_selection_only(RESIDENT_KEY, self.app_cards[RESIDENT_KEY])

            if self._notification_enabled:
                own_icon = QIcon(str(get_icon_path())) if get_icon_path() else QIcon()
                self._show_notification(
                    tr("msg_config_switched"),
                    tr("app_title"),
                    app_icon=own_icon
                )

            self._loading = True
            QTimer.singleShot(0, lambda: self._deferred_load_tab_config(app_config))

        except Exception:
            self._switching_config = False
            raise

    def _capture_config_from_tabs(self, device_type):
        if device_type == "output":
            tab = self.output_tab
        else:
            tab = self.input_tab

        device_name = tab.get_device_name()
        preamp = tab.get_preamp_gain()
        mode = tab.current_mode
        variable_freqs = list(tab._variable_freqs) if hasattr(tab, '_variable_freqs') and tab._variable_freqs else None
        freqs, gains = tab.get_filter_gains()
        gain_map = {float(freq): gain for freq, gain in zip(freqs, gains)}
        left_bal, right_bal = tab.get_channel_balance()

        eq_type = self._auto_eq_type.get(device_type, "GraphicEQ")
        raw_content = self._auto_eq_raw_content.get(device_type, None)

        return {
            "device_name": device_name,
            "preamp": preamp,
            "mode": mode,
            "variable_freqs": variable_freqs,
            "gain_map": gain_map,
            "channel_balance": {"left": left_bal, "right": right_bal},
            "eq_type": eq_type,
            "raw_content": raw_content
        }

    def _load_app_config_to_tabs(self, app_config):
        out_cfg = app_config.get("output", {})
        in_cfg = app_config.get("input", {})

        for tab in (self.output_tab, self.input_tab):
            tab._loading = True
            tab.setUpdatesEnabled(False)

        try:
            if out_cfg:
                t0 = time.perf_counter()
                self._load_tab_config(self.output_tab, out_cfg)
                self.logger.debug(f"[CPU探针]   output_tab: {(time.perf_counter()-t0)*1000:.1f}ms")
            if in_cfg:
                t0 = time.perf_counter()
                self._load_tab_config(self.input_tab, in_cfg)
                self.logger.debug(f"[CPU探针]   input_tab: {(time.perf_counter()-t0)*1000:.1f}ms")
        finally:
            for tab in (self.output_tab, self.input_tab):
                tab._loading = False
                tab.setUpdatesEnabled(True)

    def _load_tab_config(self, tab, cfg):
        device_name = cfg.get("device_name")
        if device_name:
            tab.set_device_by_name(device_name)
            tab.set_device_enabled(True)

        preamp = cfg.get("preamp", 0.0)
        tab.set_preamp_gain(preamp)

        gain_map = cfg.get("gain_map", {})
        if gain_map:
            converted_map = {float(k): v for k, v in gain_map.items()}
            new_freqs = sorted(converted_map.keys())
            if (hasattr(tab, 'current_freqs') and tab.current_freqs and
                    list(tab.current_freqs) == new_freqs and tab.bands):
                tab.set_filter_gains(converted_map)
            else:
                tab.set_frequencies_from_gain_map(converted_map)
        else:
            mode = cfg.get("mode", "15频段")
            var_freqs = cfg.get("variable_freqs")
            if (hasattr(tab, 'current_mode') and tab.current_mode == mode and
                    (mode != '可变频段' or var_freqs == getattr(tab, '_variable_freqs', None))):
                pass
            else:
                tab.set_mode_and_freqs(mode, var_freqs)

        bal = cfg.get("channel_balance", {})
        if bal:
            tab._left_balance = bal.get("left", 0.0)
            tab._right_balance = bal.get("right", 0.0)

        eq_type = cfg.get("eq_type", "GraphicEQ")
        raw_content = cfg.get("raw_content", None)
        tab._auto_eq_type = eq_type
        tab._auto_eq_raw_content = raw_content if eq_type in ("ParametricEQ", "FixedBandEQ") else None
        self._auto_eq_type[tab.device_type] = eq_type
        if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
            self._auto_eq_raw_content[tab.device_type] = raw_content
        else:
            self._auto_eq_raw_content.pop(tab.device_type, None)

    def _create_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.tab_widget = QTabWidget()
        self.output_tab = EQTab('output', self)
        self.input_tab = EQTab('input', self)
        self.tab_widget.addTab(self.output_tab, tr("tab_speaker"))
        self.tab_widget.setTabIcon(0, _create_speaker_icon())
        self.tab_widget.addTab(self.input_tab, tr("tab_microphone"))
        self.tab_widget.setTabIcon(1, _create_microphone_icon())

        self.output_tab.monitorStateChanged.connect(lambda idx: self._save_monitor_state('output', idx))
        self.input_tab.monitorStateChanged.connect(lambda idx: self._save_monitor_state('input', idx))

        self.config_tab = QWidget()
        self.tab_widget.addTab(self.config_tab, tr("tab_config"))
        self.tab_widget.setTabIcon(2, _create_config_icon())
        self._create_config_tab()

        self.extensions_tab = ExtensionsPage(self)
        self.tab_widget.addTab(self.extensions_tab, tr("tab_extensions"))
        self.tab_widget.setTabIcon(3, _create_extensions_icon())

        self.settings_tab = QWidget()
        self.tab_widget.addTab(self.settings_tab, tr("tab_settings"))
        self.tab_widget.setTabIcon(4, _create_settings_icon())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(16)

        card_cfg, layout_cfg, self._title_cfg = self._create_settings_card(tr("card_config_management"))
        folder_row = QHBoxLayout()
        self.select_folder_btn = QPushButton(tr("btn_select_config_folder"))
        self.select_folder_btn.clicked.connect(self._select_eqapo_directory)
        folder_row.addWidget(self.select_folder_btn)
        self.folder_path_label = QLineEdit()
        self.folder_path_label.setFrame(False)
        self.folder_path_label.setStyleSheet("color: #cccccc; border: 1px solid #555; padding: 4px; border-radius: 4px; background-color: #2d2d2d;")
        self.folder_path_label.setMinimumWidth(200)
        self.folder_path_label.setToolTip(tr("tooltip_current_config_path"))
        self.folder_path_label.setPlaceholderText(tr("placeholder_paste_path"))
        self.folder_path_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.folder_path_label.customContextMenuRequested.connect(self._on_path_context_menu)
        self.folder_path_label.returnPressed.connect(self._on_path_input_confirmed)
        self.folder_path_label.editingFinished.connect(self._on_path_input_finished)
        self.folder_path_label.textChanged.connect(self._on_path_text_changed)
        folder_row.addWidget(self.folder_path_label, 1)
        layout_cfg.addLayout(folder_row)

        install_row = QHBoxLayout()
        self.install_btn = QPushButton(tr("btn_install"))
        self.install_btn.clicked.connect(self._install_config)
        self.install_btn.setEnabled(False)
        self.uninstall_btn = QPushButton(tr("btn_uninstall"))
        self.uninstall_btn.clicked.connect(self._uninstall_config)
        self.uninstall_btn.setEnabled(False)
        install_row.addWidget(self.install_btn)
        install_row.addWidget(self.uninstall_btn)
        self.spk_switch = ToggleSwitch(tr("toggle_spk_file"))
        self.spk_switch.setChecked(self._spk_enabled)
        self.spk_switch.toggled.connect(self._on_spk_toggled)
        install_row.addWidget(self.spk_switch)
        self.mic_switch = ToggleSwitch(tr("toggle_mic_file"))
        self.mic_switch.setChecked(self._mic_enabled)
        self.mic_switch.toggled.connect(self._on_mic_toggled)
        install_row.addWidget(self.mic_switch)
        self.config_write_mode_combo = ForceDownComboBox()
        self.config_write_mode_combo.setFocusPolicy(Qt.StrongFocus)
        self.config_write_mode_combo.wheelEvent = lambda event: event.ignore()
        self.config_write_mode_combo.addItem(tr("combo_config_write_mode"), "overwrite")
        self.config_write_mode_combo.addItem(tr("combo_config_preserve_mode"), "preserve")
        self.config_write_mode_combo.setCurrentIndex(0 if self._config_write_mode == "overwrite" else 1)
        self.config_write_mode_combo.currentIndexChanged.connect(self._on_config_write_mode_changed)
        install_row.addWidget(self.config_write_mode_combo)
        install_row.addStretch()
        layout_cfg.addLayout(install_row)

        card_tools, layout_tools, self._title_tools = self._create_settings_card(tr("card_reset_maintenance"))
        tools_row = QHBoxLayout()
        reset_btn = QPushButton(tr("btn_reset_settings"))
        self.reset_btn = reset_btn
        reset_btn.clicked.connect(self._reset_all_settings)
        tools_row.addWidget(reset_btn)
        clear_logs_btn = QPushButton(tr("btn_clear_logs"))
        self.clear_logs_btn = clear_logs_btn
        clear_logs_btn.clicked.connect(self._clear_log_files)
        tools_row.addWidget(clear_logs_btn)
        open_log_folder_btn = QPushButton(tr("btn_open_logs"))
        self.open_log_folder_btn = open_log_folder_btn
        open_log_folder_btn.clicked.connect(self._open_log_folder)
        tools_row.addWidget(open_log_folder_btn)
        tools_row.addStretch()
        layout_tools.addLayout(tools_row)

        card_app, layout_app, self._title_app = self._create_settings_card(tr("card_app_behavior"))
        self.tray_checkbox = ToggleSwitch(tr("toggle_tray"))
        self.tray_checkbox.setChecked(self.tray_enabled)
        self.tray_checkbox.toggled.connect(self._on_tray_checkbox_toggled)
        layout_app.addWidget(self.tray_checkbox)

        self.startup_checkbox = ToggleSwitch(tr("toggle_startup"))
        self.startup_checkbox.setChecked(self.automatic_startup.is_enabled())
        self.startup_checkbox.toggled.connect(self._on_startup_checkbox_toggled)
        layout_app.addWidget(self.startup_checkbox)

        card_lang, layout_lang, self._title_lang = self._create_settings_card(tr("card_language"))
        lang_row = QHBoxLayout()
        lang_label = QLabel(tr("label_interface_language"))
        self.lang_label = lang_label
        layout_lang.addWidget(lang_label)
        self.lang_combo = ForceDownComboBox()
        self.lang_combo.setFocusPolicy(Qt.StrongFocus)
        self.lang_combo.wheelEvent = lambda event: event.ignore()
        self.lang_combo.addItem(tr("lang_zh_CN"), "zh_CN")
        self.lang_combo.addItem(tr("lang_zh_TW"), "zh_TW")
        self.lang_combo.addItem(tr("lang_en"), "en")
        current_lang = self.config_manager.get_language()
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == current_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        layout_lang.addWidget(self.lang_combo)
        layout_lang.addStretch()

        scroll_layout.addWidget(card_lang)
        scroll_layout.addWidget(card_cfg)
        scroll_layout.addWidget(card_tools)
        scroll_layout.addWidget(card_app)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        settings_outer = QVBoxLayout(self.settings_tab)
        settings_outer.setContentsMargins(0, 0, 0, 0)
        settings_outer.addWidget(scroll)

        self.output_tab.anythingChanged.connect(self._on_any_value_changed)
        self.input_tab.anythingChanged.connect(self._on_any_value_changed)

        self.output_tab.AutoEQRequested.connect(self.openAutoEQDialog)
        self.output_tab.ChannelBalanceRequested.connect(self.openChannelBalanceDialog)
        self.input_tab.AutoEQRequested.connect(self.openAutoEQDialog)
        self.input_tab.ChannelBalanceRequested.connect(self.openChannelBalanceDialog)

        self.output_tab.deviceRefreshRequested.connect(self._refresh_audio_devices)
        self.input_tab.deviceRefreshRequested.connect(self._refresh_audio_devices)

        main_layout.addWidget(self.tab_widget)

    def _clear_log_files(self):
        log_dir = APP_DIR / "logs"
        if not log_dir.exists():
            QMessageBox.information(self, tr("dialog_info"), tr("msg_no_log_dir"))
            return

        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            QMessageBox.information(self, tr("dialog_info"), tr("msg_no_log_files"))
            return

        delete_names = {"Wrong.log", "Downloads.log"}
        success_count = 0
        failed_files = []
        for f in log_files:
            try:
                if f.name in delete_names:
                    f.unlink()
                else:
                    with open(f, 'w'):
                        pass
                success_count += 1
            except Exception as e:
                failed_files.append(f.name)
                self.logger.warning(f"清空日志文件失败 {f}: {e}")

        if failed_files:
            QMessageBox.warning(
                self, tr("dialog_partial_failure"),
                tr("msg_cannot_clear") + "\n".join(failed_files)
            )
        else:
            dialog = QDialog(self)
            dialog.setWindowTitle(tr("dialog_success"))
            layout = QVBoxLayout(dialog)
            label = QLabel(tr("msg_logs_cleared"))
            layout.addWidget(label)
            button_box = QDialogButtonBox(QDialogButtonBox.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)
            dialog.setMinimumWidth(200)
            dialog.exec()

    def _open_log_folder(self):
        log_dir = APP_DIR / "logs"
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
        url = QUrl.fromLocalFile(str(log_dir))
        QDesktopServices.openUrl(url)

    def _save_monitor_state(self, device_type, state):
        if self.config_manager.get_monitor_state(device_type) != state:
            self.config_manager.set_monitor_state(device_type, state)
            self.logger.debug(f"保存监听状态: monitor_state_{device_type}={state}")

    def _refresh_audio_devices(self):
        from PySide6.QtMultimedia import QMediaDevices
        outputs = QMediaDevices.audioOutputs()
        inputs = QMediaDevices.audioInputs()
        self.output_tab.set_device_list(outputs)
        self.input_tab.set_device_list(inputs)
        self.logger.debug("刷新音频设备列表")

    @staticmethod
    def apply_dark_theme(app):
        if app is None:
            return
        app.setStyle("Fusion")

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(20, 20, 20))
        palette.setColor(QPalette.AlternateBase, QColor(42, 42, 42))
        palette.setColor(QPalette.ToolTipBase, QColor(30, 30, 30))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(136, 136, 136))
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        app.setPalette(palette)

        dark_style = """
        * { font-size: 9pt; }
        QMainWindow, QDialog { background-color: #1e1e1e; }
        QLabel { color: #ffffff; }
        QPushButton {
            background-color: #333333;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 12px;
            color: #ffffff;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #404040; border-color: #666666; }
        QPushButton:pressed { background-color: #2a2a2a; }
        QPushButton:disabled { background-color: #2a2a2a; color: #808080; border-color: #444444; }

        QComboBox {
            background-color: #2d2d2d;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 4px 8px;
            color: #ffffff;
            min-height: 20px;
        }
        QComboBox:hover { border-color: #777777; }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border-left: 1px solid #555555;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }
        QComboBox::down-arrow {
            width: 12px;
            height: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            border: 1px solid #555555;
            selection-background-color: #0078D4;
            selection-color: white;
        }

        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
            background-color: #2d2d2d;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 4px;
            color: #ffffff;
            selection-background-color: #0078D4;
            selection-color: white;
        }
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #888888;
        }

        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-position: top right;
            width: 16px;
            height: 14px;
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-left: none;
            border-top-right-radius: 4px;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-position: bottom right;
            width: 16px;
            height: 14px;
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-left: none;
            border-bottom-right-radius: 4px;
        }

        QSlider::groove:vertical {
            border: 1px solid #444444;
            background: #3a3a3a;
            width: 8px;
            border-radius: 4px;
        }
        QSlider::handle:vertical {
            background: #0078D4;
            border: 1px solid #005a9e;
            height: 20px;
            width: 16px;
            margin: 0 -4px;
            border-radius: 8px;
        }
        QSlider::handle:vertical:hover { background: #1E90FF; }
        QSlider::sub-page:vertical { background: #3a3a3a; border-radius: 4px; }

        QSlider::groove:horizontal {
            border: 1px solid #444444;
            background: #3a3a3a;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #0078D4;
            border: 1px solid #005a9e;
            width: 20px;
            height: 16px;
            margin: -4px 0;
            border-radius: 8px;
        }
        QSlider::handle:horizontal:hover { background: #1E90FF; }
        QSlider::sub-page:horizontal { background: #3a3a3a; border-radius: 4px; }

        QProgressBar {
            border: 1px solid #555555;
            border-radius: 4px;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #0078D4;
            border-radius: 3px;
        }

        QTabWidget::pane {
            border: 1px solid #444444;
            background-color: #1e1e1e;
            border-radius: 4px;
        }
        QTabBar::tab {
            background-color: #2d2d2d;
            border: 1px solid #444444;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
            color: #cccccc;
        }
        QTabBar::tab:selected {
            background-color: #3a3a3a;
            border-bottom-color: #3a3a3a;
            color: white;
        }
        QTabBar::tab:hover:!selected { background-color: #3a3a3a; }

        QScrollBar:vertical {
            border: none;
            background: #2a2a2a;
            width: 14px;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical {
            background: #0078D4;
            min-height: 20px;
            border-radius: 7px;
        }
        QScrollBar::handle:vertical:hover {
            background: #1E90FF;
        }
        QScrollBar::sub-line, QScrollBar::add-line {
            width: 0px;
            height: 0px;
            border: none;
            background: none;
        }

        QScrollBar:horizontal {
            border: none;
            background: #2a2a2a;
            height: 14px;
            border-radius: 7px;
        }
        QScrollBar::handle:horizontal {
            background: #0078D4;
            min-width: 20px;
            border-radius: 7px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #1E90FF;
        }
        QScrollBar::sub-line, QScrollBar::add-line {
            width: 0px;
            height: 0px;
            border: none;
            background: none;
        }

        QTableWidget {
            background-color: #1e1e1e;
            alternate-background-color: #1e1e1e;
            gridline-color: #444444;
            border: none;
            color: #ffffff;
        }
        QTableWidget::item {
            padding: 6px;
        }
        QTableWidget::item:selected {
            background-color: #0078D4;
            color: white;
        }
        QHeaderView::section {
            background-color: #1e1e1e;
            border: 1px solid #444444;
            padding: 4px;
            color: #cccccc;
        }

        QListView::item:selected,
        QTreeView::item:selected {
            background-color: #0078D4;
            color: white;
        }

        QToolBar {
            background-color: #1e1e1e;
            border-bottom: 1px solid #444444;
            spacing: 4px;
            padding: 4px;
        }
        QToolButton {
            background-color: transparent;
            border: none;
            border-radius: 4px;
            padding: 4px;
            color: #ffffff;
        }
        QToolButton:hover { background-color: #404040; }
        QToolButton:pressed { background-color: #505050; }

        QMenu::item:selected {
            background-color: #0078D4;
            border-radius: 4px;
            color: white;
        }

        QFrame#settingsCard {
            background-color: #252525;
            border: 1px solid #3a3a3a;
            border-radius: 8px;
        }
        QLabel#settingsCardTitle {
            font-size: 11pt;
            font-weight: bold;
            color: #e0e0e0;
        }

        QScrollArea {
            background-color: transparent;
            border: none;
        }

        QCheckBox {
            color: #cccccc;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #2d2d2d;
        }
        QCheckBox::indicator:checked {
            background-color: #0078D4;
            border-color: #0078D4;
        }
        QCheckBox::indicator:hover {
            border-color: #888888;
        }
        """
        app.setStyleSheet(dark_style)

    def safe_read_file(self, file_path: Path, max_retries=3, retry_delay=0.2):
        for attempt in range(max_retries):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.readlines()
            except (PermissionError, OSError) as e:
                self.logger.warning(f"读取文件失败 (尝试 {attempt + 1}/{max_retries}): {file_path}, 错误: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
        return []

    def _backup_default_config(self):
        self.default_backup_dir.mkdir(parents=True, exist_ok=True)

        if self.config_path and self.config_path.exists():
            default_cfg = self.default_backup_dir / "config.txt"
            if not default_cfg.exists():
                try:
                    shutil.copy2(self.config_path, default_cfg)
                    self.logger.info(f"默认配置已备份到 {default_cfg}")
                except Exception as e:
                    self.logger.error(f"备份默认 config.txt 失败: {e}")

    def _reset_all_settings(self):
        self._block_save = True
        self.save_timer.stop()

        watched_paths = self.file_watcher.files()
        if watched_paths:
            self.file_watcher.removePaths(watched_paths)

        self.logger.info("重置所有设置")

        if self.config_path and self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                before = f.read(200)
            self.logger.info(f"恢复前 config.txt 前200字符: {before}")

        default_cfg = self.default_backup_dir / "config.txt"
        if default_cfg.exists():
            try:
                shutil.copy2(default_cfg, self.config_path)
                self.logger.info("已从默认备份还原 config.txt")
            except Exception as e:
                self.logger.error(f"还原 config.txt 失败: {e}")
        else:
            reply = QMessageBox.question(
                self,
                tr("msg_no_default_backup"),
                tr("msg_no_default_backup_detail"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                try:
                    open(self.config_path, 'w').close()
                    self.logger.info("用户选择清空 config.txt")
                except Exception as e:
                    self.logger.error(f"清空 config.txt 失败: {e}")
            else:
                self.logger.info("用户选择保留当前 config.txt")

        for dev_path in [self.output_device_path, self.input_device_path]:
            if dev_path and dev_path.exists():
                try:
                    self._ignored_paths.add(str(dev_path))
                    dev_path.unlink()
                    self.logger.info(f"已删除 {dev_path.name}")
                except Exception as e:
                    self.logger.error(f"删除 {dev_path} 失败: {e}")

        self._loading = True
        self.output_tab.reset_to_default()
        self.input_tab.reset_to_default()

        self.output_left_balance = 0.0
        self.output_right_balance = 0.0
        self.input_left_balance = 0.0
        self.input_right_balance = 0.0

        self._refresh_audio_devices()
        self._loading = False

        self.config_manager.clear_all()

        if hasattr(self, 'app_config_manager'):
            self.app_config_manager.clear_all_app_configs()

        if hasattr(self, 'app_detector'):
            self.app_detector.stop()
            self.app_detector._configured_paths.clear()

        for card in list(self.app_cards.values()):
            index = self.apps_layout.indexOf(card)
            if index != -1:
                self.apps_layout.removeWidget(card)
            card.deleteLater()
        self.app_cards.clear()

        self._selected_app_path = None

        self._auto_switch_enabled = False
        self._notification_enabled = False
        self._resident_config_enabled = False
        self._exclude_default_config = False
        self._last_configured_pid = None
        self._exclude_retry_app_path = None
        self._exclude_retry_pid = None
        self._exclude_retry_count = 0
        self._stop_exclude_retry()
        if hasattr(self, 'auto_switch_switch'):
            self.auto_switch_switch.blockSignals(True)
            self.auto_switch_switch.setChecked(False)
            self.auto_switch_switch.blockSignals(False)
        if hasattr(self, 'resident_config_switch'):
            self.resident_config_switch.blockSignals(True)
            self.resident_config_switch.setChecked(False)
            self.resident_config_switch.blockSignals(False)
        if hasattr(self, 'exclude_default_switch'):
            self.exclude_default_switch.blockSignals(True)
            self.exclude_default_switch.setChecked(False)
            self.exclude_default_switch.blockSignals(False)
        if hasattr(self, 'notification_switch'):
            self.notification_switch.blockSignals(True)
            self.notification_switch.setChecked(False)
            self.notification_switch.blockSignals(False)

        self.tray_enabled = False
        if hasattr(self, 'tray_checkbox'):
            self.tray_checkbox.blockSignals(True)
            self.tray_checkbox.setChecked(False)
            self.tray_checkbox.blockSignals(False)
        if hasattr(self, 'startup_checkbox'):
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(False)
            self.startup_checkbox.blockSignals(False)
        self.automatic_startup.disable()

        self.other_lines = []
        self._set_config_path(None)

        self._block_save = False
        self.logger.info("重置设置完成")

    def _on_any_value_changed(self):
        if self._loading or self._block_save:
            return
        self.save_timer.start()

    def _on_file_changed(self, path):
        self.logger.debug(f"检测到文件变化: {path}")
        if path in self._ignored_paths:
            self.logger.debug(f"路径在忽略列表中，跳过: {path}")
            self._ignored_paths.discard(path)
            return
        path_obj = Path(path).resolve()
        config_resolved = self.config_path.resolve() if self.config_path else None
        output_resolved = self.output_device_path.resolve() if self.output_device_path else None
        input_resolved = self.input_device_path.resolve() if self.input_device_path else None
        if (config_resolved and path_obj == config_resolved) or \
                (output_resolved and path_obj == output_resolved) or \
                (input_resolved and path_obj == input_resolved):
            self.logger.debug(f"触发重载定时器")
            self.file_change_timer.start()
        else:
            self.logger.debug(f"路径不匹配任何监控文件，忽略")

    def _safe_write_string(self, file_path: Path, content: str, max_retries=3, retry_delay=0.2):
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"直接写入成功: {file_path}")
            return True
        except PermissionError:
            self.logger.debug(f"直接写入失败，尝试临时文件策略: {file_path}")
        except Exception as e:
            self.logger.warning(f"直接写入异常: {e}，尝试临时文件策略")

        temp_name = f".tmp_{uuid.uuid4().hex}{file_path.suffix}"
        temp_path = file_path.with_name(temp_name)

        for attempt in range(max_retries):
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                temp_path.replace(file_path)
                self.logger.info(f"临时文件替换成功 (尝试 {attempt + 1}/{max_retries}): {file_path}")
                return True
            except PermissionError as e:
                self.logger.info(f"替换失败 (attempt {attempt + 1}/{max_retries}): {e}")
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                time.sleep(retry_delay * (attempt + 1))
            except Exception as e:
                self.logger.exception(f"临时文件替换异常: {e}")
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                return False

        self.logger.warning("临时文件替换多次失败，尝试重命名原文件...")
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        try:
            if backup_path.exists():
                backup_path.unlink()
            file_path.rename(backup_path)
            temp_path.rename(file_path)
            backup_path.unlink(missing_ok=True)
            self.logger.info(f"重命名替换成功: {file_path}")
            return True
        except PermissionError as e:
            self.logger.error(f"重命名替换也失败: {e}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if backup_path.exists() and not file_path.exists():
                backup_path.rename(file_path)
        except Exception as e:
            self.logger.exception(f"重命名替换异常: {e}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        self.logger.error(f"无法写入文件: {file_path}，所有写入策略均失败")
        return False

    def safe_write_file(self, file_path: Path, lines, max_retries=3, retry_delay=0.2):
        content = '\n'.join(line.rstrip('\n') for line in lines)
        return self._safe_write_string(file_path, content, max_retries, retry_delay)

    def _write_file_if_changed(self, file_path, new_lines):
        file_path = Path(file_path)
        new_content = '\n'.join(line.rstrip('\n') for line in new_lines)

        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                old_lines = old_content.splitlines()
                old_content_norm = '\n'.join(old_lines)
                if old_content_norm == new_content:
                    self.logger.debug(f"文件内容未变化，跳过写入: {file_path}")
                    return True
            except Exception as e:
                self.logger.warning(f"读取旧文件失败，将强制写入: {e}")

        return self.safe_write_file(file_path, new_lines)

    def _set_config_path(self, path):
        if self.config_path and self.file_watcher.files():
            self.file_watcher.removePaths(self.file_watcher.files())
        self.config_path = path
        if path:
            self.file_watcher.addPath(str(path))
            self.output_device_path = path.parent / "SPK.txt"
            self.input_device_path = path.parent / "MIC.txt"
            if self.output_device_path.exists():
                self.file_watcher.addPath(str(self.output_device_path))
            if self.input_device_path.exists():
                self.file_watcher.addPath(str(self.input_device_path))
            self.logger.info(f"当前配置: {path.name}")
            self._last_modified_times[str(path)] = path.stat().st_mtime
            if self.output_device_path and self.output_device_path.exists():
                self._last_modified_times[str(self.output_device_path)] = self.output_device_path.stat().st_mtime
            if self.input_device_path and self.input_device_path.exists():
                self._last_modified_times[str(self.input_device_path)] = self.input_device_path.stat().st_mtime

        if hasattr(self, 'folder_path_label'):
            self._updating_path_label = True
            if self.config_path:
                self.folder_path_label.setText(str(self.config_path))
                self.folder_path_label.setToolTip(str(self.config_path))
                self.install_btn.setEnabled(True)
                self.uninstall_btn.setEnabled(True)
            else:
                self.folder_path_label.clear()
                self.folder_path_label.setToolTip("")
                self.install_btn.setEnabled(False)
                self.uninstall_btn.setEnabled(False)
            self._updating_path_label = False

    def _sync_file_watcher(self):
        current_files = set(self.file_watcher.files())
        target_files = {str(self.config_path)}
        if self.output_device_path and self.output_device_path.exists():
            target_files.add(str(self.output_device_path))
        if self.input_device_path and self.input_device_path.exists():
            target_files.add(str(self.input_device_path))
        to_remove = current_files - target_files
        if to_remove:
            self.file_watcher.removePaths(list(to_remove))
        to_add = target_files - current_files
        if to_add:
            self.file_watcher.addPaths(list(to_add))
        self.logger.debug(f"文件监视器已同步: {target_files}")

    def _parse_device_file_to_dict(self, file_path):
        if not file_path or not file_path.exists():
            return None, None, {}, None, None, "GraphicEQ", None

        try:
            lines = self.safe_read_file(file_path)
        except Exception as e:
            self.logger.exception(f"读取设备文件 {file_path} 失败")
            return None, None, {}, None, None, "GraphicEQ", None

        device_name = None
        preamp = None
        gain_map = {}
        mode = None
        variable_freqs = None
        eq_type = "GraphicEQ"
        raw_content = None
        raw_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('#'):
                lower_stripped = stripped.lower()
                if lower_stripped.startswith('# eqmode:'):
                    mode_part = stripped[len('# EQMode:'):].strip()
                    if mode_part == '15频段':
                        mode_part = '15频段'
                    elif mode_part == '31频段':
                        mode_part = '31频段'
                    mode = mode_part
                elif lower_stripped.startswith('# variablefreqs:'):
                    freqs_part = stripped[len('# VariableFreqs:'):].strip()
                    if freqs_part:
                        try:
                            variable_freqs = [float(f) for f in freqs_part.split()]
                        except ValueError:
                            pass
                continue

            lower = stripped.lower()
            if lower.startswith('device:'):
                parts = stripped.split()
                if len(parts) >= 2:
                    full_device_str = ' '.join(parts[1:]).strip().strip('"')
                    guid = extract_guid(full_device_str)
                    device_name = guid if guid else full_device_str
            elif lower.startswith('preamp:'):
                parts = stripped.split()
                if len(parts) >= 2:
                    try:
                        preamp = float(parts[1])
                    except ValueError:
                        pass
            elif lower.startswith('filter:'):
                if eq_type == "GraphicEQ":
                    eq_type = "ParametricEQ"
                raw_lines.append(line)
                parts = stripped.split()
                fc_index = next((i for i, p in enumerate(parts) if p.lower() == 'fc'), None)
                gain_index = next((i for i, p in enumerate(parts) if p.lower() == 'gain'), None)
                if fc_index is not None and gain_index is not None:
                    try:
                        if fc_index + 1 < len(parts):
                            freq = float(parts[fc_index + 1])
                        else:
                            continue
                        if gain_index + 1 < len(parts):
                            gain = float(parts[gain_index + 1])
                        else:
                            continue
                        gain_map[freq] = gain
                    except (ValueError, IndexError):
                        continue
                else:
                    continue
            elif lower.startswith('graphiceq:'):
                content = line[line.find(':') + 1:].strip()
                if not content:
                    continue
                segments = content.split(';')
                for seg in segments:
                    seg = seg.strip()
                    if not seg:
                        continue
                    tokens = seg.split()
                    if len(tokens) >= 2:
                        try:
                            freq = float(tokens[0])
                            gain = float(tokens[1])
                            gain_map[freq] = gain
                        except ValueError:
                            pass

        if raw_lines:
            raw_content = '\n'.join(raw_lines) + '\n'

        self.logger.debug(f"解析设备文件 {file_path}: device={device_name}, preamp={preamp}, eq_type={eq_type}, 频段数={len(gain_map)}")
        return device_name, preamp, gain_map, mode, variable_freqs, eq_type, raw_content

    def _parse_device_file_channel_balance(self, file_path):
        if not file_path or not file_path.exists():
            return None, None

        try:
            lines = self.safe_read_file(file_path)
        except Exception:
            return None, None

        left_balance = None
        right_balance = None
        current_channel = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            lower = stripped.lower()
            if lower.startswith('channel:'):
                parts = stripped.split()
                if len(parts) >= 2:
                    ch = parts[1].strip().upper()
                    current_channel = ch
            elif lower.startswith('preamp:') and current_channel:
                parts = stripped.split()
                if len(parts) >= 2:
                    try:
                        gain = float(parts[1])
                        if current_channel == 'L':
                            left_balance = gain
                        elif current_channel == 'R':
                            right_balance = gain
                    except ValueError:
                        pass

        return left_balance, right_balance

    def _load_config_from_file(self):
        if not self.config_path or not self.config_path.exists():
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_file_not_found", path=self.config_path))
            self.logger.error(f"配置文件不存在: {self.config_path}")
            return

        self._refresh_audio_devices()
        self.logger.info(f"开始加载配置文件: {self.config_path}")

        try:
            lines = self.safe_read_file(self.config_path)
        except Exception as e:
            self.logger.exception("读取主配置文件失败")
            QMessageBox.critical(self, tr("dialog_error"), tr("msg_cannot_read_file", error=str(e)))
            return

        new_output_device_name = None
        new_input_device_name = None
        new_output_preamp = 0.0
        new_input_preamp = 0.0
        new_output_gain_map = {}
        new_input_gain_map = {}
        new_output_mode = '15频段'
        new_input_mode = '15频段'
        new_output_variable_freqs = EQTab.DEFAULT_VARIABLE_FREQS.copy()
        new_input_variable_freqs = EQTab.DEFAULT_VARIABLE_FREQS.copy()
        new_output_left_balance = 0.0
        new_output_right_balance = 0.0
        new_input_left_balance = 0.0
        new_input_right_balance = 0.0
        new_other_lines = []
        new_output_eq_type = "GraphicEQ"
        new_input_eq_type = "GraphicEQ"
        new_output_raw_lines = []
        new_input_raw_lines = []

        current_ctx = None
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                continue

            if stripped.startswith('#'):
                new_other_lines.append(line)
                i += 1
                continue

            lower = stripped.lower()
            if lower.startswith('include:'):
                parts = stripped.split()
                if len(parts) >= 2:
                    inc_file = parts[1].strip().strip('"')
                    if inc_file == "SPK" or inc_file == "SPK.txt":
                        inc_path = self.config_path.parent / inc_file
                        dev_name, preamp, gain_map, mode, var_freqs, eq_type, raw_content = self._parse_device_file_to_dict(inc_path)
                        if dev_name is not None:
                            new_output_device_name = dev_name
                        if preamp is not None:
                            new_output_preamp = preamp
                        new_output_gain_map.update(gain_map)
                        if mode is not None:
                            new_output_mode = mode
                        if var_freqs is not None:
                            new_output_variable_freqs = var_freqs
                        if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
                            self._auto_eq_type['output'] = eq_type
                            self._auto_eq_raw_content['output'] = raw_content
                        left_bal, right_bal = self._parse_device_file_channel_balance(inc_path)
                        if left_bal is not None:
                            new_output_left_balance = left_bal
                        if right_bal is not None:
                            new_output_right_balance = right_bal
                    elif inc_file == "MIC" or inc_file == "MIC.txt":
                        inc_path = self.config_path.parent / inc_file
                        dev_name, preamp, gain_map, mode, var_freqs, eq_type, raw_content = self._parse_device_file_to_dict(inc_path)
                        if dev_name is not None:
                            new_input_device_name = dev_name
                        if preamp is not None:
                            new_input_preamp = preamp
                        new_input_gain_map.update(gain_map)
                        if mode is not None:
                            new_input_mode = mode
                        if var_freqs is not None:
                            new_input_variable_freqs = var_freqs
                        if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
                            self._auto_eq_type['input'] = eq_type
                            self._auto_eq_raw_content['input'] = raw_content
                        left_bal, right_bal = self._parse_device_file_channel_balance(inc_path)
                        if left_bal is not None:
                            new_input_left_balance = left_bal
                        if right_bal is not None:
                            new_input_right_balance = right_bal
                i += 1
                continue
            elif lower.startswith('device:'):
                parts = stripped.split()
                if len(parts) >= 2:
                    full_device_str = ' '.join(parts[1:]).strip().strip('"')
                    guid = extract_guid(full_device_str)
                    dev_name = guid if guid else full_device_str
                    if current_ctx is None:
                        if new_output_device_name is None:
                            new_output_device_name = dev_name
                            current_ctx = 'output'
                        elif new_input_device_name is None:
                            new_input_device_name = dev_name
                            current_ctx = 'input'
                        else:
                            pass
                    elif current_ctx == 'output':
                        new_output_device_name = dev_name
                    elif current_ctx == 'input':
                        new_input_device_name = dev_name
                i += 1
                continue
            elif lower.startswith('preamp:'):
                gain = 0.0
                parts = stripped.split()
                if len(parts) >= 2:
                    try:
                        gain = float(parts[1])
                    except ValueError:
                        pass
                if current_ctx == 'output':
                    new_output_preamp = gain
                elif current_ctx == 'input':
                    new_input_preamp = gain
                else:
                    new_output_preamp = gain
                i += 1
                continue
            elif lower.startswith('filter:'):
                parts = stripped.split()
                try:
                    fc_index = next((i for i, p in enumerate(parts) if p.lower() == 'fc'), None)
                    gain_index = next((i for i, p in enumerate(parts) if p.lower() == 'gain'), None)
                    if fc_index is not None and gain_index is not None:
                        if fc_index + 1 < len(parts):
                            freq_str = parts[fc_index + 1]
                            freq = float(freq_str)
                        else:
                            i += 1
                            continue
                        if gain_index + 1 < len(parts):
                            gain = float(parts[gain_index + 1])
                        else:
                            i += 1
                            continue
                    else:
                        i += 1
                        continue
                except (ValueError, IndexError):
                    i += 1
                    continue
                if current_ctx == 'output':
                    new_output_gain_map[freq] = gain
                    new_output_eq_type = "ParametricEQ"
                    new_output_raw_lines.append(line)
                elif current_ctx == 'input':
                    new_input_gain_map[freq] = gain
                    new_input_eq_type = "ParametricEQ"
                    new_input_raw_lines.append(line)
                else:
                    new_output_gain_map[freq] = gain
                    new_output_eq_type = "ParametricEQ"
                    new_output_raw_lines.append(line)
                i += 1
                continue
            elif lower.startswith('graphiceq:'):
                content = line[line.find(':') + 1:].strip()
                if content:
                    segments = content.split(';')
                    for seg in segments:
                        seg = seg.strip()
                        if not seg:
                            continue
                        tokens = seg.split()
                        if len(tokens) >= 2:
                            try:
                                freq = float(tokens[0])
                                gain = float(tokens[1])
                                if current_ctx == 'output' or current_ctx is None:
                                    new_output_gain_map[freq] = gain
                                elif current_ctx == 'input':
                                    new_input_gain_map[freq] = gain
                            except ValueError:
                                pass
                i += 1
                continue
            else:
                i += 1
                continue

        self.output_device_name = self.config_manager.get_output_device_name() or new_output_device_name
        self.input_device_name = self.config_manager.get_input_device_name() or new_input_device_name
        self.output_preamp = self.config_manager.get_output_preamp() or new_output_preamp
        self.input_preamp = self.config_manager.get_input_preamp() or new_input_preamp
        self.output_gain_map = self.config_manager.get_output_gain_map() or new_output_gain_map
        self.input_gain_map = self.config_manager.get_input_gain_map() or new_input_gain_map
        self.output_mode = self.config_manager.get_output_mode() or new_output_mode
        self.input_mode = self.config_manager.get_input_mode() or new_input_mode
        self.output_variable_freqs = self.config_manager.get_output_variable_freqs() or new_output_variable_freqs
        self.input_variable_freqs = self.config_manager.get_input_variable_freqs() or new_input_variable_freqs
        self.output_left_balance = new_output_left_balance or self.config_manager.get_output_channel_balance()[0]
        self.output_right_balance = new_output_right_balance or self.config_manager.get_output_channel_balance()[1]
        self.input_left_balance = new_input_left_balance or self.config_manager.get_input_channel_balance()[0]
        self.input_right_balance = new_input_right_balance or self.config_manager.get_input_channel_balance()[1]
        self.other_lines = new_other_lines

        if 'output' not in self._auto_eq_type and new_output_eq_type != "GraphicEQ" and new_output_raw_lines:
            self._auto_eq_type['output'] = new_output_eq_type
            self._auto_eq_raw_content['output'] = '\n'.join(new_output_raw_lines) + '\n'
        if 'input' not in self._auto_eq_type and new_input_eq_type != "GraphicEQ" and new_input_raw_lines:
            self._auto_eq_type['input'] = new_input_eq_type
            self._auto_eq_raw_content['input'] = '\n'.join(new_input_raw_lines) + '\n'

        self._loading = True

        self.output_tab.set_device_by_name(self.output_device_name)
        self.input_tab.set_device_by_name(self.input_device_name)
        self.output_tab.set_preamp_gain(self.output_preamp)
        self.input_tab.set_preamp_gain(self.input_preamp)
        self.output_tab.set_channel_balance(self.output_left_balance, self.output_right_balance)
        self.input_tab.set_channel_balance(self.input_left_balance, self.input_right_balance)

        if self.output_gain_map:
            self.output_tab.set_frequencies_from_gain_map(self.output_gain_map)
        else:
            self.output_tab.set_mode_and_freqs(self.output_mode, self.output_variable_freqs)

        if self.input_gain_map:
            self.input_tab.set_frequencies_from_gain_map(self.input_gain_map)
        else:
            self.input_tab.set_mode_and_freqs(self.input_mode, self.input_variable_freqs)

        output_monitor = self.config_manager.get_monitor_state("output")
        input_monitor = self.config_manager.get_monitor_state("input")
        self.output_tab.monitor_combo.setCurrentIndex(output_monitor)
        self.input_tab.monitor_combo.setCurrentIndex(input_monitor)

        self._loading = False
        self.logger.info(f"已加载 {self.config_path.name}，保留注释行")

        QApplication.processEvents()
        self._sync_file_watcher()

        self._last_modified_times[str(self.config_path)] = self.config_path.stat().st_mtime
        if self.output_device_path and self.output_device_path.exists():
            self._last_modified_times[str(self.output_device_path)] = self.output_device_path.stat().st_mtime
        if self.input_device_path and self.input_device_path.exists():
            self._last_modified_times[str(self.input_device_path)] = self.input_device_path.stat().st_mtime

    def _generate_device_file_content(self, tab):
        if not tab.is_device_enabled():
            return []
        audio_dev = tab.get_audio_device()
        if audio_dev is None or audio_dev.isNull():
            self.logger.debug(f"设备 {tab.device_type} 不可用（无效设备），不生成内容")
            return []
        dev_id = tab.get_device_id()
        if not dev_id:
            return []

        lines = []
        device_desc = tab.get_device_name()
        if device_desc and device_desc != tr("label_no_device_found"):
            device_desc_clean = re.sub(r'[\(\)\{\}]', '', device_desc).strip()
        else:
            device_desc_clean = None

        guid = extract_guid(dev_id)
        write_id = guid if guid else dev_id

        if device_desc_clean:
            lines.append(f"Device: {device_desc_clean} {write_id}\n")
        else:
            lines.append(f"Device: {write_id}\n")

        preamp_gain = tab.get_preamp_gain()
        if abs(preamp_gain) > 1e-6:
            lines.append(f"Preamp: {preamp_gain:.1f} dB\n")

        eq_type = self._auto_eq_type.get(tab.device_type, None)
        raw_content = self._auto_eq_raw_content.get(tab.device_type, None)
        if eq_type is None:
            eq_type = getattr(tab, '_auto_eq_type', "GraphicEQ")
        if raw_content is None:
            raw_content = getattr(tab, '_auto_eq_raw_content', None)

        if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
            for line in raw_content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                lower = stripped.lower()
                if lower.startswith('preamp:') or lower.startswith('device:'):
                    continue
                lines.append(stripped + "\n")
        else:
            freqs, gains = tab.get_filter_gains()
            has_nonzero_gain = any(abs(g) > 1e-6 for g in gains)
            if has_nonzero_gain:
                freq_gain_pairs = []
                for f, g in zip(freqs, gains):
                    freq_str = str(int(f)) if f == int(f) else f"{f:.1f}"
                    gain_str = f"{g:+.1f}"
                    freq_gain_pairs.append(f"{freq_str} {gain_str}")
                lines.append("GraphicEQ: " + "; ".join(freq_gain_pairs) + "\n")

        left_balance, right_balance = tab.get_channel_balance()
        if abs(left_balance) > 1e-6 or abs(right_balance) > 1e-6:
            lines.append(f"Channel: L\n")
            lines.append(f"Preamp: {left_balance:.1f} dB\n")
            lines.append(f"Channel: R\n")
            lines.append(f"Preamp: {right_balance:.1f} dB\n")

        return lines

    def _save_config(self):
        try:
            if self._switching_config or self._loading:
                return
            if self.config_path:
                self._save_config_to_path(self.config_path)
                if self._resident_config_enabled and self._selected_app_path == RESIDENT_KEY:
                    self._save_config_to_resident()
                elif self._selected_app_path and self._selected_app_path != RESIDENT_KEY:
                    self._save_config_to_app(self._selected_app_path)
            else:
                if self.output_tab is None or self.input_tab is None:
                    return
                self.output_device_name = self.output_tab.get_device_name()
                self.input_device_name = self.input_tab.get_device_name()
                self.output_preamp = self.output_tab.get_preamp_gain()
                self.input_preamp = self.input_tab.get_preamp_gain()
                self.output_mode = self.output_tab.current_mode
                self.input_mode = self.input_tab.current_mode
                self.output_variable_freqs = self.output_tab._variable_freqs
                self.input_variable_freqs = self.input_tab._variable_freqs
                freqs, gains = self.output_tab.get_filter_gains()
                self.output_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}
                freqs, gains = self.input_tab.get_filter_gains()
                self.input_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}

                out_monitor = self.output_tab.monitor_combo.currentIndex()
                in_monitor = self.input_tab.monitor_combo.currentIndex()
                if self.config_manager.get_monitor_state("output") != out_monitor:
                    self.config_manager.set_monitor_state("output", out_monitor)
                if self.config_manager.get_monitor_state("input") != in_monitor:
                    self.config_manager.set_monitor_state("input", in_monitor)

                self.config_manager.set_output_device_name(self.output_device_name)
                self.config_manager.set_output_preamp(self.output_preamp)
                self.config_manager.set_output_mode(self.output_mode)
                self.config_manager.set_output_variable_freqs(self.output_variable_freqs)
                self.config_manager.set_output_gain_map(self.output_gain_map)

                self.config_manager.set_input_device_name(self.input_device_name)
                self.config_manager.set_input_preamp(self.input_preamp)
                self.config_manager.set_input_mode(self.input_mode)
                self.config_manager.set_input_variable_freqs(self.input_variable_freqs)
                self.config_manager.set_input_gain_map(self.input_gain_map)

                self.config_manager.sync()

                self.logger.info("已保存设置到settings.ini文件")

                if self._resident_config_enabled and self._selected_app_path == RESIDENT_KEY:
                    self._save_config_to_resident()
                elif self._selected_app_path and self._selected_app_path != RESIDENT_KEY:
                    self._save_config_to_app(self._selected_app_path)
        except Exception:
            self.logger.exception("保存配置时发生异常")

    def _save_config_to_path(self, path):
        try:
            if self.output_tab is None or self.input_tab is None:
                return
            self.output_device_name = self.output_tab.get_device_name()
            self.input_device_name = self.input_tab.get_device_name()
            self.output_preamp = self.output_tab.get_preamp_gain()
            self.input_preamp = self.input_tab.get_preamp_gain()
            self.output_mode = self.output_tab.current_mode
            self.input_mode = self.input_tab.current_mode
            self.output_variable_freqs = self.output_tab._variable_freqs
            self.input_variable_freqs = self.input_tab._variable_freqs
            freqs, gains = self.output_tab.get_filter_gains()
            self.output_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}
            freqs, gains = self.input_tab.get_filter_gains()
            self.input_gain_map = {freq: gain for freq, gain in zip(freqs, gains)}
            self.output_left_balance, self.output_right_balance = self.output_tab.get_channel_balance()
            self.input_left_balance, self.input_right_balance = self.input_tab.get_channel_balance()

            out_lines = self._generate_device_file_content(self.output_tab)
            in_lines = self._generate_device_file_content(self.input_tab)

            if self.output_tab.is_device_enabled() and not out_lines:
                self.logger.warning("扬声器设备已启用但无法生成有效配置，将注释其Include行")
            if self.input_tab.is_device_enabled() and not in_lines:
                self.logger.warning("麦克风设备已启用但无法生成有效配置，将注释其Include行")

            paths_to_ignore = [str(self.config_path)]
            if self.output_device_path and self.output_device_path.exists():
                paths_to_ignore.append(str(self.output_device_path))
            if self.input_device_path and self.input_device_path.exists():
                paths_to_ignore.append(str(self.input_device_path))
            self._ignored_paths.update(paths_to_ignore)
            self._clear_ignore_timer.start(500)

            if out_lines:
                if self._spk_enabled:
                    if not self._write_file_if_changed(self.output_device_path, out_lines):
                        self.logger.error(f"无法写入输出设备文件: {self.output_device_path}")
                        return
                else:
                    if self.output_device_path and self.output_device_path.exists():
                        try:
                            self.output_device_path.unlink()
                            self.logger.info(f"已删除 SPK 文件: {self.output_device_path}")
                        except Exception as e:
                            self.logger.error(f"删除 SPK 文件失败: {e}")

            if in_lines:
                if self._mic_enabled:
                    if not self._write_file_if_changed(self.input_device_path, in_lines):
                        self.logger.error(f"无法写入输入设备文件: {self.input_device_path}")
                        return
                else:
                    if self.input_device_path and self.input_device_path.exists():
                        try:
                            self.input_device_path.unlink()
                            self.logger.info(f"已删除 MIC 文件: {self.input_device_path}")
                        except Exception as e:
                            self.logger.error(f"删除 MIC 文件失败: {e}")

            if self._config_write_mode == "preserve":
                lines = []
                has_spk_include = False
                has_mic_include = False
                if self.config_path.exists():
                    try:
                        with open(self.config_path, 'r', encoding='utf-8') as f:
                            existing_lines = f.read().splitlines()
                    except Exception:
                        existing_lines = []
                    for line in existing_lines:
                        stripped = line.strip()
                        if re.search(r'^\s*#?\s*include\s*:\s*spk\.txt', stripped, re.IGNORECASE):
                            has_spk_include = True
                            if self._spk_enabled:
                                lines.append("Include: SPK.txt" if out_lines else "# Include: SPK.txt")
                            else:
                                continue
                        elif re.search(r'^\s*#?\s*include\s*:\s*mic\.txt', stripped, re.IGNORECASE):
                            has_mic_include = True
                            if self._mic_enabled:
                                lines.append("Include: MIC.txt" if in_lines else "# Include: MIC.txt")
                            else:
                                continue
                        else:
                            lines.append(line)
                if not has_spk_include and self._spk_enabled:
                    lines.append("Include: SPK.txt" if out_lines else "# Include: SPK.txt")
                if not has_mic_include and self._mic_enabled:
                    lines.append("Include: MIC.txt" if in_lines else "# Include: MIC.txt")
            else:
                lines = []
                for line in self.other_lines:
                    if re.search(r'include\s*:\s*(spk\.txt|mic\.txt)', line, re.IGNORECASE):
                        continue
                    lines.append(line)

                if self._spk_enabled:
                    lines.append("Include: SPK.txt\n" if out_lines else "# Include: SPK.txt\n")
                if self._mic_enabled:
                    lines.append("Include: MIC.txt\n" if in_lines else "# Include: MIC.txt\n")

            if not self._write_file_if_changed(self.config_path, lines):
                self.logger.error(f"无法写入主配置文件: {self.config_path}")
                return

            self._last_modified_times[str(self.config_path)] = self.config_path.stat().st_mtime
            if self.output_device_path and self.output_device_path.exists():
                self._last_modified_times[str(self.output_device_path)] = self.output_device_path.stat().st_mtime
            if self.input_device_path and self.input_device_path.exists():
                self._last_modified_times[str(self.input_device_path)] = self.input_device_path.stat().st_mtime

            out_monitor = self.output_tab.monitor_combo.currentIndex()
            in_monitor = self.input_tab.monitor_combo.currentIndex()
            if self.config_manager.get_monitor_state("output") != out_monitor:
                self.config_manager.set_monitor_state("output", out_monitor)
            if self.config_manager.get_monitor_state("input") != in_monitor:
                self.config_manager.set_monitor_state("input", in_monitor)

            self.config_manager.set_output_device_name(self.output_device_name)
            self.config_manager.set_output_preamp(self.output_preamp)
            self.config_manager.set_output_mode(self.output_mode)
            self.config_manager.set_output_variable_freqs(self.output_variable_freqs)
            self.config_manager.set_output_gain_map(self.output_gain_map)
            self.config_manager.set_output_channel_balance(self.output_left_balance, self.output_right_balance)

            self.config_manager.set_input_device_name(self.input_device_name)
            self.config_manager.set_input_preamp(self.input_preamp)
            self.config_manager.set_input_mode(self.input_mode)
            self.config_manager.set_input_variable_freqs(self.input_variable_freqs)
            self.config_manager.set_input_gain_map(self.input_gain_map)
            self.config_manager.set_input_channel_balance(self.input_left_balance, self.input_right_balance)

            self.config_manager.sync()

            self.logger.info(f"已保存到 {self.config_path.name}")
        except Exception:
            self.logger.exception("保存配置到文件时发生异常")

    def _on_path_context_menu(self, pos):
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078D4;
                border-radius: 4px;
            }
        """)
        copy_action = QAction(tr("menu_copy"), self)
        copy_action.triggered.connect(self.folder_path_label.copy)
        menu.addAction(copy_action)
        paste_action = QAction(tr("menu_paste"), self)
        paste_action.triggered.connect(self.folder_path_label.paste)
        menu.addAction(paste_action)
        cut_action = QAction(tr("menu_cut"), self)
        cut_action.triggered.connect(self.folder_path_label.cut)
        menu.addAction(cut_action)
        delete_action = QAction(tr("menu_delete"), self)
        delete_action.triggered.connect(self.folder_path_label.del_)
        menu.addAction(delete_action)
        menu.exec(self.folder_path_label.mapToGlobal(pos))

    def _on_path_input_confirmed(self):
        self._validate_path_input()

    def _on_path_input_finished(self):
        if self.folder_path_label.hasFocus():
            return
        self._validate_path_input()

    def _on_path_text_changed(self):
        if hasattr(self, '_updating_path_label') and self._updating_path_label:
            return
        if not hasattr(self, '_path_validate_timer'):
            self._path_validate_timer = QTimer()
            self._path_validate_timer.setSingleShot(True)
            self._path_validate_timer.timeout.connect(self._validate_path_input)
        self._path_validate_timer.start(300)

    def _validate_path_input(self):
        text = self.folder_path_label.text().strip()
        if not text:
            return
        path = Path(text)
        if path.is_file() and path.name.lower() == "config.txt":
            self._set_config_path(path)
            self.logger.info(f"已通过输入设置配置文件: {path}")
        elif path.is_dir():
            candidates = [
                path / "config" / "config.txt",
                path / "config.txt"
            ]
            for cand in candidates:
                if cand.is_file():
                    self._set_config_path(cand)
                    self.logger.info(f"已通过输入设置配置文件: {cand}")
                    return
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_config_not_found_in_dir"))
        else:
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_invalid_config_path"))

    def _select_eqapo_directory(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialog_select_apo_dir"),
            QDir.rootPath()
        )
        if not folder:
            return

        folder_path = Path(folder)
        candidates = [
            folder_path / "config" / "config.txt",
            folder_path / "config.txt"
        ]
        found_config = None
        for cand in candidates:
            if cand.is_file():
                found_config = cand
                break

        if found_config:
            self._set_config_path(found_config)
            self.logger.info(f"已选择配置文件: {found_config}")
            return

        reply = QMessageBox.question(
            self,
            tr("dialog_no_config_found"),
            tr("msg_config_not_found_ask_manual"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            self._updating_path_label = True
            self.folder_path_label.clear()
            self._updating_path_label = False
            self.folder_path_label.setToolTip("")
            self.install_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog_select_config_txt"),
            str(folder_path),
            tr("file_filter_config_txt")
        )
        if not file_path:
            return

        config_file = Path(file_path)
        if config_file.name.lower() == "config.txt" and config_file.exists():
            self._set_config_path(config_file)
            self.logger.info(f"已手动选择配置文件: {config_file}")
        else:
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_select_valid_config"))
            self._updating_path_label = True
            self.folder_path_label.clear()
            self._updating_path_label = False
            self.folder_path_label.setToolTip("")
            self.install_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)

    def _install_config(self):
        if not self.config_path:
            QMessageBox.warning(self, tr("dialog_warning"), tr("msg_select_apo_dir_first"))
            return
        self._backup_default_config()
        self._save_config()
        self.config_manager.set_last_config_path(str(self.config_path))
        self.config_manager.set_last_apo_path(str(self.config_path.parent.parent))
        QMessageBox.information(self, tr("dialog_install_complete"), tr("msg_config_installed"))

    def _uninstall_config(self):
        if not self.config_path:
            return

        reply = QMessageBox.question(
            self,
            tr("dialog_confirm_uninstall"),
            tr("msg_uninstall_warning"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._block_save = True
        self.save_timer.stop()

        self.output_tab._stop_monitor()
        self.input_tab._stop_monitor()

        watched_paths = self.file_watcher.files()
        if watched_paths:
            self.file_watcher.removePaths(watched_paths)

        paths_to_ignore = [str(self.config_path)]
        if self.output_device_path and self.output_device_path.exists():
            paths_to_ignore.append(str(self.output_device_path))
        if self.input_device_path and self.input_device_path.exists():
            paths_to_ignore.append(str(self.input_device_path))
        self._ignored_paths.update(paths_to_ignore)

        for dev_path in [self.output_device_path, self.input_device_path]:
            if dev_path and dev_path.exists():
                try:
                    dev_path.unlink()
                    self.logger.info(f"已删除 {dev_path}")
                except Exception as e:
                    self.logger.error(f"删除 {dev_path} 失败: {e}")

        config_restored = False
        default_cfg = self.default_backup_dir / "config.txt"
        if default_cfg.exists():
            try:
                backup_content = default_cfg.read_text(encoding='utf-8')
                lines = backup_content.splitlines(keepends=True)
                if self._write_file_if_changed(self.config_path, lines):
                    self.logger.info("已从备份还原 config.txt")
                    config_restored = True
                else:
                    QMessageBox.warning(self, tr("dialog_error"), tr("msg_cannot_write_config"))
            except Exception as e:
                self.logger.exception("还原 config.txt 失败")
                QMessageBox.warning(self, tr("dialog_error"), tr("msg_restore_config_error", e=e))
        else:
            reply2 = QMessageBox.question(
                self,
                tr("msg_no_default_backup"),
                tr("msg_no_default_backup_detail"),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply2 == QMessageBox.Yes:
                try:
                    open(self.config_path, 'w').close()
                    self.logger.info("已清空 config.txt")
                    config_restored = True
                except Exception as e:
                    QMessageBox.warning(self, tr("dialog_error"), tr("msg_clear_config_error", e=e))
            else:
                self.logger.info("用户取消清空 config.txt")

        self._do_uninstall_reset()

        if config_restored:
            QMessageBox.information(self, tr("dialog_uninstall_complete"), tr("msg_uninstalled_restored"))
        else:
            QMessageBox.information(self, tr("dialog_uninstall_complete"), tr("msg_uninstalled_no_restore"))

    def _do_uninstall_reset(self):
        self._loading = True
        self.output_tab.reset_to_default()
        self.input_tab.reset_to_default()

        self.output_left_balance = 0.0
        self.output_right_balance = 0.0
        self.input_left_balance = 0.0
        self.input_right_balance = 0.0

        self.config_manager.clear_all()

        if hasattr(self, 'app_config_manager'):
            self.app_config_manager.clear_all_app_configs()

        if hasattr(self, 'app_detector'):
            self.app_detector.stop()
            self.app_detector._configured_paths.clear()

        for card in list(self.app_cards.values()):
            index = self.apps_layout.indexOf(card)
            if index != -1:
                self.apps_layout.removeWidget(card)
            card.deleteLater()
        self.app_cards.clear()
        self._selected_app_path = None

        self._auto_switch_enabled = False
        self._notification_enabled = False
        self._resident_config_enabled = False
        self._exclude_default_config = False
        self._last_configured_pid = None
        self._exclude_retry_app_path = None
        self._exclude_retry_pid = None
        self._exclude_retry_count = 0
        self._stop_exclude_retry()
        self._spk_enabled = True
        self._mic_enabled = True
        if hasattr(self, 'auto_switch_switch'):
            self.auto_switch_switch.blockSignals(True)
            self.auto_switch_switch.setChecked(False)
            self.auto_switch_switch.blockSignals(False)
        if hasattr(self, 'resident_config_switch'):
            self.resident_config_switch.blockSignals(True)
            self.resident_config_switch.setChecked(False)
            self.resident_config_switch.blockSignals(False)
        if hasattr(self, 'exclude_default_switch'):
            self.exclude_default_switch.blockSignals(True)
            self.exclude_default_switch.setChecked(False)
            self.exclude_default_switch.blockSignals(False)
        if hasattr(self, 'notification_switch'):
            self.notification_switch.blockSignals(True)
            self.notification_switch.setChecked(False)
            self.notification_switch.blockSignals(False)
        if hasattr(self, 'spk_switch'):
            self.spk_switch.blockSignals(True)
            self.spk_switch.setChecked(True)
            self.spk_switch.blockSignals(False)
        if hasattr(self, 'mic_switch'):
            self.mic_switch.blockSignals(True)
            self.mic_switch.setChecked(True)
            self.mic_switch.blockSignals(False)
        if hasattr(self, 'config_write_mode_combo'):
            self.config_write_mode_combo.blockSignals(True)
            self.config_write_mode_combo.setCurrentIndex(0)
            self.config_write_mode_combo.blockSignals(False)
        self._config_write_mode = "overwrite"
        self.config_manager.set_config_write_mode("overwrite")

        self.tray_enabled = False
        if hasattr(self, 'tray_checkbox'):
            self.tray_checkbox.blockSignals(True)
            self.tray_checkbox.setChecked(False)
            self.tray_checkbox.blockSignals(False)
        if hasattr(self, 'startup_checkbox'):
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(False)
            self.startup_checkbox.blockSignals(False)
        self.automatic_startup.disable()

        self.other_lines = []
        self._set_config_path(None)

        self._refresh_audio_devices()
        self._loading = False

        if self.config_path:
            self._sync_file_watcher()
        self._block_save = False

    def openAutoEQDialog(self, device_type):
        self._current_auto_eq_device = device_type
        dlg = AutoEQDialog(self, app_path=self._selected_app_path)
        self._auto_eq_dialog = dlg
        dlg.dataReady.connect(self.applyAutoEQData)
        result = dlg.exec()
        if hasattr(dlg, 'download_worker') and dlg.download_worker is not None:
            dlg.download_worker.requestInterruption()
            dlg.download_worker.wait(2000)
        if hasattr(dlg, 'scan_worker') and dlg.scan_worker is not None:
            dlg.scan_worker.requestInterruption()
            dlg.scan_worker.wait(2000)
        self._auto_eq_dialog = None

    def applyAutoEQData(self, preamp, gain_map_json, eq_type="GraphicEQ", raw_content=None):
        try:
            gain_map = json.loads(gain_map_json)
        except json.JSONDecodeError:
            self.logger.exception("接收到的 AutoEQ 数据格式错误")
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_data_format_error"))
            return

        device = self._current_auto_eq_device

        if device == 'output':
            self.output_tab.set_preamp_gain(preamp)
            self.output_tab.set_frequencies_from_gain_map(gain_map)
            self.output_tab._auto_eq_type = eq_type
            self.output_tab._auto_eq_raw_content = raw_content if eq_type in ("ParametricEQ", "FixedBandEQ") else None
            self.logger.info(f"应用 AutoEQ 到输出设备，eq_type={eq_type}, preamp={preamp}, 频段数={len(gain_map)}")
        elif device == 'input':
            self.input_tab.set_preamp_gain(preamp)
            self.input_tab.set_frequencies_from_gain_map(gain_map)
            self.input_tab._auto_eq_type = eq_type
            self.input_tab._auto_eq_raw_content = raw_content if eq_type in ("ParametricEQ", "FixedBandEQ") else None
            self.logger.info(f"应用 AutoEQ 到输入设备，eq_type={eq_type}, preamp={preamp}, 频段数={len(gain_map)}")
        else:
            self.logger.warning(f"未知设备类型: {self._current_auto_eq_device}")
            return

        if device:
            self._auto_eq_type[device] = eq_type
            if eq_type in ("ParametricEQ", "FixedBandEQ") and raw_content:
                self._auto_eq_raw_content[device] = raw_content
            else:
                self._auto_eq_raw_content.pop(device, None)

        self._on_any_value_changed()

    def openChannelBalanceDialog(self, device_type):
        if device_type == 'output':
            left_gain, right_gain = self.output_tab.get_channel_balance()
        else:
            left_gain, right_gain = self.input_tab.get_channel_balance()

        dlg = ChannelBalanceDialog(left_gain, right_gain, self)
        dlg.balanceChanged.connect(lambda l, r, dt=device_type: self._applyChannelBalance(dt, l, r))
        dlg.show()

    def _applyChannelBalance(self, device_type, left_gain, right_gain):
        if device_type == 'output':
            self.output_tab.set_channel_balance(left_gain, right_gain)
        else:
            self.input_tab.set_channel_balance(left_gain, right_gain)
        self.logger.debug(f"声道平衡: {device_type} 左={left_gain}dB, 右={right_gain}dB")


def main():
    logger = logging.getLogger()
    
    def _global_excepthook(exc_type, exc_value, exc_tb):
        logger.critical("未捕获的异常:", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _global_excepthook
    
    from PySide6.QtCore import qInstallMessageHandler
    def qt_message_handler(mode, context, message):
        if "qt.multimedia.ffmpeg" not in message:
            pass
    qInstallMessageHandler(qt_message_handler)
    
    app = QApplication(sys.argv)
    
    saved_lang = config_manager.get_language()
    set_language(saved_lang)

    install_qt_translator(app)
    
    logger.info(f"当前语言: {saved_lang}")
    
    lock_temp_resources()
    
    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.info(f"应用程序图标设置成功: {icon_path}")
    else:
        logger.warning("未找到图标文件，将使用默认图标")
    
    EQAPOEditor.apply_dark_theme(app)

    window = EQAPOEditor()
    QApplication.processEvents()

    QTimer.singleShot(200, window.extensions_tab.launch_silent_apps)

    if not window.tray_enabled:
        window.show()
        window.show_hide_btn.setText(tr("tray_hide"))
    else:
        window.show_hide_btn.setText(tr("tray_show"))

    exit_code = app.exec()
    logger.info(f"程序退出，代码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception as _main_error:
        _logger.critical("程序运行过程中发生未捕获的异常", exc_info=True)
        traceback.print_exc()
        sys.exit(1)