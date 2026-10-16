from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtGui import QIcon
from pathlib import Path
import sys
import tempfile

_locked_handles = []

def _lock_file(file_path):
    try:
        f = open(file_path, 'rb')
        _locked_handles.append(f)
        return True
    except Exception:
        return False

def _is_in_temp_dir(file_path):
    try:
        temp_dir = Path(tempfile.gettempdir()).resolve()
        file_dir = Path(file_path).resolve()
        return str(file_dir).casefold().startswith(str(temp_dir).casefold())
    except Exception:
        return False

def lock_temp_resources():
    try:
        file_dir = Path(__file__).parent
        if _is_in_temp_dir(file_dir):
            for f in file_dir.iterdir():
                if f.is_file():
                    _lock_file(f)
    except Exception:
        pass

    if hasattr(sys, '_MEIPASS'):
        try:
            meipass = Path(sys._MEIPASS)
            if _is_in_temp_dir(meipass):
                for f in meipass.iterdir():
                    if f.is_file():
                        _lock_file(f)
        except Exception:
            pass

def get_icon_path():
    found = None
    is_temp = False

    exe_dir = Path(sys.executable).parent
    path = exe_dir / "EQAPO_Editor.ico"
    if path.exists():
        return path

    temp_dir = Path(__file__).parent
    path = temp_dir / "EQAPO_Editor.ico"
    if path.exists():
        found = path
        is_temp = _is_in_temp_dir(path)

    if found is None:
        app_dir = Path(__file__).parent
        path = app_dir / "EQAPO_Editor.ico"
        if path.exists():
            found = path
            is_temp = _is_in_temp_dir(path)

    if found is None and hasattr(sys, '_MEIPASS'):
        path = Path(sys._MEIPASS) / "EQAPO_Editor.ico"
        if path.exists():
            found = path
            is_temp = _is_in_temp_dir(path)

    if found is not None and is_temp:
        _lock_file(found)

    return found


class CustomWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowOpacity(1.0)

        self.setMinimumSize(800, 600)
        self.resize(900, 600)

        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(str(icon_path)))

    def center_on_screen(self):
        screen = self.screen()
        if screen is None:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(geometry.center() - self.rect().center())