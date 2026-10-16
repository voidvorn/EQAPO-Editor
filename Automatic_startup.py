import sys
import ctypes
from ctypes import wintypes
from pathlib import Path

wintypes.HRESULT = ctypes.c_long

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', wintypes.BYTE * 8)
    ]

shell32 = ctypes.WinDLL('shell32.dll', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32.dll', use_last_error=True)

GetEnvironmentVariableW = kernel32.GetEnvironmentVariableW
GetEnvironmentVariableW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, wintypes.DWORD]
GetEnvironmentVariableW.restype = wintypes.DWORD

def _get_env_var(name):
    buf_size = 32768
    buf = ctypes.create_unicode_buffer(buf_size)
    result = GetEnvironmentVariableW(name, buf, buf_size)
    if result == 0 or result > buf_size:
        return None
    return buf.value

SHGetKnownFolderPath = shell32.SHGetKnownFolderPath
SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
SHGetKnownFolderPath.restype = wintypes.HRESULT

FOLDERID_Startup = GUID(
    0x82A74AEB, 0xF869, 0x4E84, 
    (0x82, 0x94, 0x06, 0x84, 0x57, 0x0F, 0x80, 0xCA)
)


class AutomaticStartup:
    
    def __init__(self):
        self.startup_folder = self._get_startup_folder()
        self.app_path = self._get_app_path()
        self.shortcut_name = "EQAPO Editor.lnk"
        self.shortcut_path = self.startup_folder / self.shortcut_name
    
    def _get_startup_folder(self):
        path_ptr = ctypes.c_wchar_p()
        hr = SHGetKnownFolderPath(ctypes.byref(FOLDERID_Startup), 0, None, ctypes.byref(path_ptr))
        if hr != 0:
            appdata = _get_env_var('APPDATA')
            if appdata:
                return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        try:
            return Path(path_ptr.value)
        finally:
            kernel32.CoTaskMemFree(ctypes.cast(path_ptr, ctypes.c_void_p))
    
    def _get_app_path(self):
        return Path(sys.argv[0]).resolve()
    
    def is_enabled(self):
        return self.shortcut_path.exists()
    
    def enable(self):
        if self.is_enabled():
            return True
        
        try:
            try:
                import pythoncom
                from win32com.client import Dispatch
                
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(str(self.shortcut_path))
                shortcut.TargetPath = str(self.app_path)
                shortcut.WorkingDirectory = str(self.app_path.parent)
                shortcut.IconLocation = str(self.app_path)
                shortcut.Save()
                return True
            except ImportError:
                return self._create_shortcut_with_ctypes()
        except Exception:
            return False
    
    def _create_shortcut_with_ctypes(self):
        try:
            with open(self.shortcut_path, 'w', encoding='utf-16') as f:
                f.write('\xff\xfe')
                f.write('[InternetShortcut]\r\n')
                f.write(f'URL=file:///{self.app_path.as_posix()}\r\n')
                f.write('IconIndex=0\r\n')
                f.write(f'IconFile={self.app_path.as_posix()}\r\n')
            return True
        except Exception:
            return False
    
    def disable(self):
        if not self.is_enabled():
            return True
        
        try:
            self.shortcut_path.unlink()
            return True
        except Exception:
            return False