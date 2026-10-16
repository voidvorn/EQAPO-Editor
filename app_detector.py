import sys
import ctypes
from ctypes import wintypes
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QTimer

from process_detector import ProcessDetector, get_detector, ProcessInfo


try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

kernel32 = ctypes.WinDLL('kernel32.dll', use_last_error=True)
user32 = ctypes.WinDLL('user32.dll', use_last_error=True)

HANDLE = wintypes.HANDLE
DWORD = wintypes.DWORD
HWND = wintypes.HWND
BOOL = wintypes.BOOL
LPWSTR = ctypes.c_wchar_p

GetForegroundWindow = user32.GetForegroundWindow
GetForegroundWindow.restype = HWND
GetForegroundWindow.argtypes = []

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.restype = DWORD
GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]

OpenProcess = kernel32.OpenProcess
OpenProcess.restype = HANDLE
OpenProcess.argtypes = [DWORD, BOOL, DWORD]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.restype = BOOL
QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, ctypes.POINTER(DWORD)]

CloseHandle = kernel32.CloseHandle
CloseHandle.restype = BOOL
CloseHandle.argtypes = [HANDLE]

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.restype = ctypes.c_int
GetWindowTextW.argtypes = [HWND, LPWSTR, ctypes.c_int]

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.restype = ctypes.c_int
GetWindowTextLengthW.argtypes = [HWND]


_foreground_cache = {'hwnd': None, 'info': None}

def get_foreground_window_info():
    hwnd = GetForegroundWindow()
    if not hwnd:
        return None

    if hwnd == _foreground_cache['hwnd'] and _foreground_cache['info'] is not None:
        return _foreground_cache['info']

    result = {'hwnd': hwnd}

    title_len = GetWindowTextLengthW(hwnd)
    if title_len > 0:
        buf = ctypes.create_unicode_buffer(title_len + 1)
        GetWindowTextW(hwnd, buf, title_len + 1)
        result['title'] = buf.value
    else:
        result['title'] = ''

    pid = DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    result['pid'] = pid.value

    exe_path = None
    try:
        h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if h_process:
            try:
                size = DWORD(32768)
                buf = ctypes.create_unicode_buffer(32768)
                if QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                    exe_path = buf.value
            finally:
                CloseHandle(h_process)
    except Exception:
        pass

    result['exe_path'] = exe_path

    if exe_path:
        result['exe_name'] = Path(exe_path).name
    elif _HAS_PSUTIL and pid.value > 0:
        try:
            proc = psutil.Process(pid.value)
            result['exe_name'] = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            result['exe_name'] = None
    else:
        result['exe_name'] = None

    _foreground_cache['hwnd'] = hwnd
    _foreground_cache['info'] = result

    return result


class AppDetector(QObject):
    appChanged = Signal(str, str)
    appSwitchedToConfigured = Signal(str)
    appChangedFromConfigured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.AppDetector")
        self._current_exe_path = None
        self._current_exe_name = None
        self._current_pid = None
        self._detect_key = None
        self._configured_paths = set()
        self._match_cache = {}
        self._previous_in_configured = False
        self._running = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_foreground)

        self._process_detector = get_detector()

    def set_configured_apps(self, app_paths):
        self._configured_paths = {str(Path(p).resolve()) for p in app_paths}
        self._match_cache.clear()
        for p in self._configured_paths:
            self._process_detector.add_app_rule(p)
        self.logger.debug(f"已注册应用: {self._configured_paths}")

    def add_configured_app(self, app_path):
        normalized = str(Path(app_path).resolve())
        self._configured_paths.add(normalized)
        self._process_detector.add_app_rule(normalized)

    def remove_configured_app(self, app_path):
        normalized = str(Path(app_path).resolve())
        self._configured_paths.discard(normalized)
        self._process_detector.remove_app_rule(normalized)

    def add_app_aliases(self, app_path, aliases):
        normalized = str(Path(app_path).resolve())
        self._process_detector.add_aliases(normalized, aliases)

    def get_app_aliases(self, app_path):
        rule = self._process_detector.get_app_rule(app_path)
        if rule:
            return list(rule.get_all_aliases())
        return []

    def refresh_app_discovery(self, app_path=None):
        self._process_detector.refresh_discovery(app_path)

    def start(self):
        if not self._running:
            self._running = True
            self._timer.start()
            self.logger.info("应用检测器已启动")

    def stop(self):
        if self._running:
            self._running = False
            self._timer.stop()
            self.logger.info("应用检测器已停止")

    def _check_foreground(self):
        if sys.platform != 'win32':
            return

        info = get_foreground_window_info()
        if info is None:
            return

        exe_path = info.get('exe_path')
        exe_name = info.get('exe_name', '')
        pid = info.get('pid', 0)

        if not exe_path and not exe_name:
            return

        detect_key = (exe_path, pid) if exe_path else (exe_name, pid)
        if detect_key == self._detect_key:
            return
        self._detect_key = detect_key

        previous_in_configured = self._previous_in_configured

        self._current_exe_path = exe_path
        self._current_exe_name = exe_name
        self._current_pid = pid

        current_normalized = None
        current_in_configured = False

        if exe_path:
            current_normalized = str(Path(exe_path).resolve())
            current_in_configured = current_normalized in self._configured_paths

        if not current_in_configured and pid > 0:
            if pid in self._match_cache:
                cached = self._match_cache[pid]
                if cached:
                    current_in_configured = True
                    current_normalized = cached
            else:
                foreground_proc = ProcessInfo(
                    pid=pid,
                    name=exe_name or '',
                    exe_path=exe_path,
                )
                matched_path = self._process_detector.match_process_to_any_rule(foreground_proc)
                if len(self._match_cache) > 200:
                    self._match_cache.clear()
                self._match_cache[pid] = matched_path
                if matched_path:
                    current_in_configured = True
                    current_normalized = matched_path

        self.appChanged.emit(exe_name, exe_path or '')

        if previous_in_configured and not current_in_configured:
            self.appChangedFromConfigured.emit(self._current_exe_path or '')

        if current_in_configured and current_normalized:
            self.appSwitchedToConfigured.emit(current_normalized)

        self._previous_in_configured = current_in_configured

        self.logger.debug(f"前台应用切换: {exe_name} ({exe_path or 'N/A'})")

    @property
    def current_exe_path(self):
        return self._current_exe_path

    @property
    def current_exe_name(self):
        return self._current_exe_name

    @property
    def current_pid(self):
        return self._current_pid

    def get_current_info(self):
        return get_foreground_window_info()