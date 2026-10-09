import logging
import json
import subprocess
import ctypes
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame, QScrollArea, QSizePolicy,
    QMenu, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, QSettings, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap, QPen, QColor, QAction

from Translation import tr, on_language_changed

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()


def get_settings_path():
    config_dir = APP_DIR / "EQapoConfig"
    config_dir.mkdir(exist_ok=True)
    return str(config_dir / "settings.ini")


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


class ExtensionConfigManager:
    EXTENSION_LIST_KEY = "extensions/list"
    EXTENSION_PREFIX = "extensions/app/"

    def __init__(self):
        self.settings = QSettings(get_settings_path(), QSettings.IniFormat)
        self.logger = logging.getLogger(f"{__name__}.ExtensionConfigManager")

    def _make_key(self, app_path: str) -> str:
        normalized = str(Path(app_path).resolve())
        return f"{self.EXTENSION_PREFIX}{normalized}"

    def _normalize_path(self, app_path: str) -> str:
        return str(Path(app_path).resolve())

    def _get_extension_list(self) -> list:
        raw = self.settings.value(self.EXTENSION_LIST_KEY, None)
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return []
        return []

    def _set_extension_list(self, ext_list: list):
        self.settings.setValue(
            self.EXTENSION_LIST_KEY,
            json.dumps(ext_list, ensure_ascii=False)
        )
        self.settings.sync()

    def add_extension(self, app_path: str) -> bool:
        normalized = self._normalize_path(app_path)
        ext_list = self._get_extension_list()
        if normalized in ext_list:
            self.logger.info(f"扩展应用已存在: {normalized}")
            return False

        config = {
            "app_name": Path(normalized).stem,
            "app_path": normalized,
            "silent_startup": False,
        }
        key = self._make_key(normalized)
        self.settings.setValue(key, json.dumps(config, ensure_ascii=False))

        ext_list.append(normalized)
        self._set_extension_list(ext_list)
        self.settings.sync()
        self.logger.info(f"已添加扩展应用: {config['app_name']} ({normalized})")
        return True

    def remove_extension(self, app_path: str):
        normalized = self._normalize_path(app_path)
        key = self._make_key(normalized)
        self.settings.remove(key)

        ext_list = self._get_extension_list()
        if normalized in ext_list:
            ext_list.remove(normalized)
            self._set_extension_list(ext_list)

        self.settings.sync()
        self.logger.info(f"已移除扩展应用: {normalized}")

    def get_extension_config(self, app_path: str) -> dict | None:
        normalized = self._normalize_path(app_path)
        key = self._make_key(normalized)
        raw = self.settings.value(key, None)
        if raw is None:
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    def set_silent_startup(self, app_path: str, silent: bool):
        config = self.get_extension_config(app_path)
        if config is None:
            return
        config["silent_startup"] = silent
        key = self._make_key(app_path)
        self.settings.setValue(key, json.dumps(config, ensure_ascii=False))
        self.settings.sync()

    def get_all_extensions(self) -> list:
        ext_list = self._get_extension_list()
        result = []
        for app_path in ext_list:
            config = self.get_extension_config(app_path)
            if config is not None:
                result.append(config)
            else:
                result.append({
                    "app_name": Path(app_path).stem,
                    "app_path": app_path,
                    "silent_startup": False,
                })
        return result

    def clear_all(self):
        for app_path in list(self._get_extension_list()):
            key = self._make_key(app_path)
            self.settings.remove(key)
        self.settings.remove(self.EXTENSION_LIST_KEY)
        self.settings.sync()


class AppLauncher:

    @staticmethod
    def launch(app_path: str) -> tuple[bool, str]:
        path = Path(app_path)
        if not path.exists():
            return False, tr("msg_file_not_found", path=app_path)

        try:
            if sys.platform == "win32":
                return AppLauncher._launch_windows(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
                return True, ""
            else:
                subprocess.Popen(["xdg-open", str(path)])
                return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _launch_windows(path: Path) -> tuple[bool, str]:
        try:
            subprocess.Popen(
                [str(path)],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, ""
        except Exception:
            pass

        try:
            SW_SHOWNORMAL = 1
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "open",
                str(path),
                None,
                None,
                SW_SHOWNORMAL
            )
            if result <= 32:
                error_codes = {
                    2: tr("err_shell_exec_file_not_found"),
                    3: tr("err_shell_exec_path_not_found"),
                    5: tr("err_shell_exec_access_denied"),
                    8: tr("err_shell_exec_out_of_memory"),
                    10: tr("err_shell_exec_bad_format"),
                    11: tr("err_shell_exec_invalid_exe"),
                    26: tr("err_shell_exec_sharing_violation"),
                    27: tr("err_shell_exec_incomplete_assoc"),
                    28: tr("err_shell_exec_dde_timeout"),
                    29: tr("err_shell_exec_dde_fail"),
                    30: tr("err_shell_exec_dde_busy"),
                    31: tr("err_shell_exec_no_assoc"),
                    32: tr("err_shell_exec_dll_not_found"),
                }
                error_msg = error_codes.get(result, tr("err_shell_exec_unknown", code=result))
                return False, tr("err_shell_exec_failed", error=error_msg)
            return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def validate_path(app_path: str) -> tuple[bool, str]:
        if not app_path or not app_path.strip():
            return False, tr("msg_path_empty")

        path = Path(app_path)

        if not path.exists():
            return False, tr("msg_path_not_exist", path=app_path)

        if not path.is_file():
            return False, tr("msg_path_not_file", path=app_path)

        ext = path.suffix.lower()
        if sys.platform == "win32":
            valid_exts = {".exe", ".bat", ".cmd", ".msc", ".lnk", ".com", ".pif"}
        elif sys.platform == "darwin":
            valid_exts = {".app", ""}
        else:
            valid_exts = set()

        if valid_exts and ext not in valid_exts:
            return False, tr("msg_unsupported_file_type", ext=ext)

        try:
            file_size = path.stat().st_size
            if file_size == 0:
                return False, tr("msg_file_size_zero")
            if file_size > 500 * 1024 * 1024:
                return False, tr("msg_file_too_large", size=f"{file_size / 1024 / 1024:.0f}")
        except OSError:
            return False, tr("msg_cannot_read_file_info")

        return True, ""


class ExtensionCard(QFrame):

    def __init__(self, app_path: str, silent_startup: bool = False, parent=None):
        super().__init__(parent)
        self.app_path = app_path
        self.app_name = Path(app_path).stem
        self._silent_startup = silent_startup

        self.setObjectName("extensionCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            #extensionCard {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 12px;
            }
            #extensionCard:hover {
                border-color: #666666;
            }
        """)

        self._init_ui()
        on_language_changed(self._retranslate_ui)

    def _retranslate_ui(self):
        self.open_btn.setText(tr("btn_open_extension"))
        self.silent_switch.setText(tr("toggle_silent_startup"))

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(10)

        name_label = QLabel(self.app_name)
        name_label.setStyleSheet("color: #cccccc; font-size: 9pt;")
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_layout.addWidget(name_label)

        self.open_btn = QPushButton(tr("btn_open_extension"))
        self.open_btn.setMinimumHeight(30)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1E90FF;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        main_layout.addWidget(self.open_btn)

        from Graphic_EQualizer import ToggleSwitch
        self.silent_switch = ToggleSwitch(tr("toggle_silent_startup"))
        self.silent_switch.setChecked(self._silent_startup)
        self.silent_switch.setToolTip("开启后开机将启动扩展应用")
        main_layout.addWidget(self.silent_switch)

        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(_create_delete_icon())
        self.delete_btn.setIconSize(QSize(14, 14))
        self.delete_btn.setFixedSize(28, 28)
        self.delete_btn.setToolTip("移除扩展应用")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a2a2a;
                border: 1px solid #6a4a4a;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #5a3a3a;
            }
        """)
        main_layout.addWidget(self.delete_btn)

    def is_silent_startup(self) -> bool:
        return self.silent_switch.isChecked()

    def set_silent_startup(self, silent: bool):
        self.silent_switch.setChecked(silent)


class ExtensionsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.ExtensionsPage")
        self.config_manager = ExtensionConfigManager()
        self._cards: dict[str, ExtensionCard] = {}

        self._init_ui()
        self._load_extensions()
        on_language_changed(self._retranslate_ui)

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.path_input = QLineEdit()
        self.path_input.setFrame(False)
        self.path_input.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 10px;
                color: #cccccc;
                min-height: 20px;
            }
        """)
        self.path_input.setPlaceholderText(tr("placeholder_ext_path"))
        self.path_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.path_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.path_input.customContextMenuRequested.connect(self._on_path_context_menu)
        self.path_input.returnPressed.connect(self._on_path_input_confirmed)
        self.path_input.textChanged.connect(self._on_path_text_changed)
        top_bar.addWidget(self.path_input)

        self.browse_btn = QPushButton(tr("btn_browse"))
        self.browse_btn.setMinimumHeight(30)
        self.browse_btn.clicked.connect(self._on_browse)
        top_bar.addWidget(self.browse_btn)

        outer_layout.addLayout(top_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 8, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        outer_layout.addWidget(self.scroll_area)

    def _retranslate_ui(self):
        self.path_input.setPlaceholderText(tr("placeholder_ext_path"))
        self.browse_btn.setText(tr("btn_browse"))

    def _on_browse(self):
        file_filter = tr("file_filter_executable")
        if sys.platform == "darwin":
            file_filter = tr("file_filter_app")

        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog_select_extension"), "", file_filter
        )

        if not file_path:
            return

        self._updating_path_input = True
        self.path_input.setText(file_path)
        self._updating_path_input = False

        valid, error = AppLauncher.validate_path(file_path)
        if not valid:
            QMessageBox.warning(self, tr("dialog_add_failed"), tr("msg_cannot_add_extension", error=error))
            return

        normalized = str(Path(file_path).resolve())
        if normalized in self._cards:
            QMessageBox.information(self, tr("dialog_info"), tr("msg_extension_exists"))
            return

        QTimer.singleShot(100, lambda: self._do_add_extension(file_path))

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
        copy_action.triggered.connect(self.path_input.copy)
        menu.addAction(copy_action)
        paste_action = QAction(tr("menu_paste"), self)
        paste_action.triggered.connect(self.path_input.paste)
        menu.addAction(paste_action)
        cut_action = QAction(tr("menu_cut"), self)
        cut_action.triggered.connect(self.path_input.cut)
        menu.addAction(cut_action)
        delete_action = QAction(tr("menu_delete"), self)
        delete_action.triggered.connect(self.path_input.del_)
        menu.addAction(delete_action)
        menu.exec(self.path_input.mapToGlobal(pos))

    def _on_path_input_confirmed(self):
        file_path = self.path_input.text().strip()
        if not file_path:
            return
        valid, error = AppLauncher.validate_path(file_path)
        if not valid:
            QMessageBox.warning(self, tr("dialog_add_failed"), tr("msg_cannot_add_extension", error=error))
            return
        normalized = str(Path(file_path).resolve())
        if normalized in self._cards:
            QMessageBox.information(self, tr("dialog_info"), tr("msg_extension_exists"))
            return
        self._do_add_extension(file_path)
        self._updating_path_input = True
        self.path_input.clear()
        self._updating_path_input = False

    def _on_path_text_changed(self):
        if hasattr(self, '_updating_path_input') and self._updating_path_input:
            return
        if not hasattr(self, '_path_validate_timer'):
            self._path_validate_timer = QTimer()
            self._path_validate_timer.setSingleShot(True)
            self._path_validate_timer.timeout.connect(
                lambda: self._validate_and_add(self.path_input.text().strip())
            )
        self._path_validate_timer.start(300)

    def _validate_and_add(self, file_path: str):
        if not file_path:
            return
        valid, error = AppLauncher.validate_path(file_path)
        if not valid:
            self.logger.warning(f"路径验证失败: {file_path} - {error}")
            return
        normalized = str(Path(file_path).resolve())
        if normalized in self._cards:
            self.logger.info(f"扩展应用已存在: {normalized}")
            return
        self._do_add_extension(file_path)
        self._updating_path_input = True
        self.path_input.clear()
        self._updating_path_input = False

    def _do_add_extension(self, app_path: str):
        try:
            success = self.config_manager.add_extension(app_path)
            if not success:
                QMessageBox.information(self, tr("dialog_info"), tr("msg_extension_exists_config"))
                return

            self._create_card(app_path, silent_startup=False)
            self._updating_path_input = True
            self.path_input.clear()
            self._updating_path_input = False
            self.logger.info(f"成功添加扩展应用: {app_path}")
        except Exception as e:
            self.logger.error(f"添加扩展应用失败: {e}", exc_info=True)
            QMessageBox.critical(self, tr("dialog_add_failed"), tr("msg_add_extension_error", error=str(e)))

    def _remove_extension(self, app_path: str):
        card = self._cards.get(app_path)
        if card is None:
            return

        reply = QMessageBox.question(
            self,
            tr("dialog_confirm_remove"),
            tr("msg_confirm_remove_extension", app_name=card.app_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self.config_manager.remove_extension(app_path)
            self.cards_layout.removeWidget(card)
            card.deleteLater()
            del self._cards[app_path]
            self.logger.info(f"成功移除扩展应用: {app_path}")
        except Exception as e:
            self.logger.error(f"移除扩展应用失败: {e}", exc_info=True)
            QMessageBox.critical(self, tr("dialog_remove_failed"), tr("msg_remove_extension_error", error=str(e)))

    def _open_extension(self, app_path: str):
        QTimer.singleShot(100, lambda: self._do_open_extension(app_path))

    def _do_open_extension(self, app_path: str):
        try:
            success, error = AppLauncher.launch(app_path)
            if success:
                self.logger.info(f"成功启动扩展应用: {app_path}")
            else:
                QMessageBox.warning(
                    self, tr("dialog_launch_failed"),
                    tr("msg_cannot_launch_extension", error=error)
                )
        except Exception as e:
            self.logger.error(f"启动扩展应用异常: {e}", exc_info=True)
            QMessageBox.critical(self, tr("dialog_launch_failed"), tr("msg_launch_extension_error", error=str(e)))

    def _on_silent_changed(self, app_path: str, silent: bool):
        try:
            self.config_manager.set_silent_startup(app_path, silent)
            self.logger.debug(f"扩展应用静默启动设置已更新: {app_path} -> {silent}")
        except Exception as e:
            self.logger.error(f"保存静默启动设置失败: {e}")

    def _create_card(self, app_path: str, silent_startup: bool = False):
        card = ExtensionCard(app_path, silent_startup, self)

        card.open_btn.clicked.connect(lambda: self._open_extension(app_path))
        card.delete_btn.clicked.connect(lambda: self._remove_extension(app_path))
        card.silent_switch.toggled.connect(
            lambda checked: self._on_silent_changed(app_path, checked)
        )

        stretch_index = self.cards_layout.count() - 1
        self.cards_layout.insertWidget(stretch_index, card)
        self._cards[app_path] = card

    def _load_extensions(self):
        try:
            extensions = self.config_manager.get_all_extensions()
            for ext in extensions:
                self._create_card(
                    ext["app_path"],
                    silent_startup=ext.get("silent_startup", False),
                )
            self.logger.info(f"已加载 {len(extensions)} 个扩展应用")
        except Exception as e:
            self.logger.error(f"加载扩展应用失败: {e}", exc_info=True)

    def get_silent_startup_apps(self) -> list:
        return [
            app_path for app_path, card in self._cards.items()
            if card.is_silent_startup()
        ]

    def launch_silent_apps(self):
        for app_path, card in self._cards.items():
            if card.is_silent_startup():
                success, error = AppLauncher.launch(app_path)
                if not success:
                    self.logger.warning(
                        f"静默启动扩展应用失败: {card.app_name} - {error}"
                    )
                else:
                    self.logger.info(f"静默启动扩展应用: {card.app_name}")

    def cleanup(self):
        for app_path, card in list(self._cards.items()):
            try:
                card.open_btn.clicked.disconnect()
                card.delete_btn.clicked.disconnect()
                card.silent_switch.toggled.disconnect()
            except (TypeError, RuntimeError):
                pass
        self._cards.clear()
        self.logger.debug("ExtensionsPage 资源已清理")