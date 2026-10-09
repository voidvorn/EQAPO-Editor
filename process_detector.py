import sys
import re
import time
import logging
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Callable, Tuple, Union
from enum import Enum, auto

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL('kernel32.dll', use_last_error=True)
psapi = ctypes.WinDLL('psapi.dll', use_last_error=True)

HANDLE = wintypes.HANDLE
DWORD = wintypes.DWORD
LONG = wintypes.LONG
BOOL = wintypes.BOOL
LPWSTR = ctypes.c_wchar_p
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001
PROCESS_ALL_ACCESS = 0x1F0FFF

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", LONG),
        ("dwFlags", DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.restype = HANDLE
CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]

Process32FirstW = kernel32.Process32FirstW
Process32FirstW.restype = BOOL
Process32FirstW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]

Process32NextW = kernel32.Process32NextW
Process32NextW.restype = BOOL
Process32NextW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]

OpenProcess = kernel32.OpenProcess
OpenProcess.restype = HANDLE
OpenProcess.argtypes = [DWORD, BOOL, DWORD]

CloseHandle = kernel32.CloseHandle
CloseHandle.restype = BOOL
CloseHandle.argtypes = [HANDLE]

QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.restype = BOOL
QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, ctypes.POINTER(DWORD)]

GetModuleBaseNameW = psapi.GetModuleBaseNameW
GetModuleBaseNameW.restype = DWORD
GetModuleBaseNameW.argtypes = [HANDLE, HANDLE, LPWSTR, DWORD]

GetProcessImageFileNameW = psapi.GetProcessImageFileNameW
GetProcessImageFileNameW.restype = DWORD
GetProcessImageFileNameW.argtypes = [HANDLE, LPWSTR, DWORD]

EnumProcesses = psapi.EnumProcesses
EnumProcesses.restype = BOOL
EnumProcesses.argtypes = [ctypes.POINTER(DWORD), DWORD, ctypes.POINTER(DWORD)]


class MatchMode(Enum):
    EXACT = auto()
    ALIAS = auto()
    WILDCARD = auto()
    REGEX = auto()
    PATH = auto()
    PATH_CONTAINS = auto()
    COMMAND_LINE = auto()
    AUTO = auto()


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    name: str
    exe_path: Optional[str] = None
    parent_pid: Optional[int] = None
    thread_count: Optional[int] = None
    command_line: Optional[str] = None
    _name_lower: Optional[str] = field(default=None, init=False, repr=False)

    @property
    def name_lower(self) -> str:
        if self._name_lower is None:
            self._name_lower = self.name.lower() if self.name else ''
        return self._name_lower

    @property
    def exe_name(self) -> str:
        return self.name

    @property
    def path_name(self) -> Optional[str]:
        if self.exe_path:
            return Path(self.exe_path).name
        return None

    def to_dict(self) -> dict:
        return {
            'pid': self.pid,
            'name': self.name,
            'exe_path': self.exe_path,
            'parent_pid': self.parent_pid,
            'thread_count': self.thread_count,
            'command_line': self.command_line,
        }


@dataclass
class AppRule:
    app_path: str
    app_name: str = ""
    aliases: List[str] = field(default_factory=list)
    match_modes: List[MatchMode] = field(default_factory=lambda: [MatchMode.AUTO])
    wildcard_patterns: List[str] = field(default_factory=list)
    regex_patterns: List[str] = field(default_factory=list)
    path_fragments: List[str] = field(default_factory=list)
    command_keywords: List[str] = field(default_factory=list)
    auto_discovered_aliases: Set[str] = field(default_factory=set)
    last_seen_processes: Dict[int, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.app_name and self.app_path:
            self.app_name = Path(self.app_path).stem
        if not self.aliases:
            self.aliases = [Path(self.app_path).name]

    def get_all_aliases(self) -> Set[str]:
        all_aliases = set(a.lower() for a in self.aliases)
        all_aliases.update(a.lower() for a in self.auto_discovered_aliases)
        return all_aliases

    def to_dict(self) -> dict:
        return {
            'app_path': self.app_path,
            'app_name': self.app_name,
            'aliases': self.aliases,
            'match_modes': [m.name for m in self.match_modes],
            'wildcard_patterns': self.wildcard_patterns,
            'regex_patterns': self.regex_patterns,
            'path_fragments': self.path_fragments,
            'command_keywords': self.command_keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AppRule':
        rule = cls(
            app_path=data.get('app_path', ''),
            app_name=data.get('app_name', ''),
            aliases=data.get('aliases', []),
            wildcard_patterns=data.get('wildcard_patterns', []),
            regex_patterns=data.get('regex_patterns', []),
            path_fragments=data.get('path_fragments', []),
            command_keywords=data.get('command_keywords', []),
        )
        mode_names = data.get('match_modes', ['AUTO'])
        rule.match_modes = [MatchMode[m] for m in mode_names if m in MatchMode.__members__]
        if not rule.match_modes:
            rule.match_modes = [MatchMode.AUTO]
        return rule


class ProcessDetector:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ProcessDetector")
        self._rules: Dict[str, AppRule] = {}
        self._cache: Dict[str, tuple[List[ProcessInfo], float]] = {}
        self._cache_ttl: float = 1.5
        self._proc_cache: Dict[Optional[frozenset], tuple[float, List[ProcessInfo]]] = {}
        self._process_list_cache_ttl: float = 2.0
        self._pid_path_cache: Dict[int, tuple[float, Optional[str]]] = {}
        self._PID_FAILED = object()
        self._pid_path_cache_ttl: float = 300.0

    def add_app_rule(self, app_path: str, **kwargs) -> AppRule:
        normalized = str(Path(app_path).resolve())
        if normalized in self._rules:
            rule = self._rules[normalized]
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
        else:
            rule = AppRule(app_path=normalized, **kwargs)
            self._rules[normalized] = rule

        if not kwargs.get('aliases') or MatchMode.AUTO in rule.match_modes:
            self._auto_discover_aliases(normalized)

        self._invalidate_cache()
        self.logger.debug(f"已注册应用规则: {Path(normalized).name} (别名: {rule.get_all_aliases()})")
        return rule

    def remove_app_rule(self, app_path: str):
        normalized = str(Path(app_path).resolve())
        if normalized in self._rules:
            del self._rules[normalized]
            self._invalidate_cache()
            self.logger.debug(f"已移除应用规则: {Path(normalized).name}")

    def get_app_rule(self, app_path: str) -> Optional[AppRule]:
        normalized = str(Path(app_path).resolve())
        return self._rules.get(normalized)

    def add_aliases(self, app_path: str, aliases: List[str]):
        rule = self.get_app_rule(app_path)
        if rule:
            for alias in aliases:
                if alias not in rule.aliases:
                    rule.aliases.append(alias)
            self._invalidate_cache()
            self.logger.debug(f"为 {Path(app_path).name} 添加别名: {aliases}")

    def is_app_running(self, app_path: str) -> bool:
        processes = self._find_app_processes(app_path)
        return len(processes) > 0

    def get_process_info(self, app_path: str) -> List[ProcessInfo]:
        return self._find_app_processes(app_path)

    def get_app_pids(self, app_path: str, force_refresh: bool = True) -> Set[int]:
        if force_refresh:
            self._invalidate_cache_for_app(app_path)

        processes = self._find_app_processes(app_path)
        return {p.pid for p in processes}

    def _invalidate_cache_for_app(self, app_path: str):
        normalized = str(Path(app_path).resolve())
        self._cache.pop(normalized, None)

    def get_all_running_processes(self, force_refresh: bool = False,
                               name_filter: Optional[Set[str]] = None) -> List[ProcessInfo]:
        now = time.time()
        cache_key = frozenset(name_filter) if name_filter else None
        if not force_refresh and cache_key in self._proc_cache:
            cached_time, cached_list = self._proc_cache[cache_key]
            if (now - cached_time) < self._process_list_cache_ttl:
                return cached_list

        processes = self._enumerate_processes(name_filter)
        self._proc_cache[cache_key] = (now, processes)
        return processes

    def find_processes_by_name(self, name: str, exact: bool = False) -> List[ProcessInfo]:
        all_procs = self.get_all_running_processes()
        name_lower = name.lower()
        if exact:
            return [p for p in all_procs if p.name_lower == name_lower]
        return [p for p in all_procs if name_lower in p.name_lower]

    def find_processes_by_path(self, path_fragment: str) -> List[ProcessInfo]:
        all_procs = self.get_all_running_processes()
        fragment_lower = path_fragment.lower()
        results = []
        for p in all_procs:
            if self._ensure_process_path(p) and fragment_lower in p.exe_path.lower():
                results.append(p)
        return results

    def _find_app_processes(self, app_path: str) -> List[ProcessInfo]:
        normalized = str(Path(app_path).resolve())
        rule = self._rules.get(normalized)

        now = time.time()
        cache_key = normalized
        if cache_key in self._cache:
            cached_results, cached_time = self._cache[cache_key]
            if (now - cached_time) < self._cache_ttl:
                return cached_results

        all_processes = self.get_all_running_processes(
            name_filter=rule.get_all_aliases() if rule else {Path(app_path).name.lower()}
        )
        matched = []

        if rule:
            matched = self._match_by_rule(rule, all_processes)
        else:
            exe_name = Path(app_path).name
            matched = self._match_by_default(app_path, exe_name, all_processes)

        self._cache[cache_key] = (matched, now)

        return matched

    def _match_by_rule(self, rule: AppRule, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        matched_pids: Set[int] = set()
        results = []

        for mode in rule.match_modes:
            for proc in processes:
                if proc.pid in matched_pids:
                    continue

                if self._match_single(proc, rule, mode):
                    matched_pids.add(proc.pid)
                    results.append(proc)

        return results

    def _match_single(self, proc: ProcessInfo, rule: AppRule, mode: MatchMode) -> bool:
        if mode == MatchMode.EXACT:
            return proc.name_lower in rule.get_all_aliases()

        elif mode == MatchMode.ALIAS:
            return proc.name_lower in rule.get_all_aliases()

        elif mode == MatchMode.WILDCARD:
            for pattern in rule.wildcard_patterns:
                if fnmatch.fnmatch(proc.name_lower, pattern.lower()):
                    return True
                if self._ensure_process_path(proc) and fnmatch.fnmatch(proc.exe_path.lower(), pattern.lower()):
                    return True
            return False

        elif mode == MatchMode.REGEX:
            for pattern in rule.regex_patterns:
                try:
                    if re.search(pattern, proc.name, re.IGNORECASE):
                        return True
                    if self._ensure_process_path(proc) and re.search(pattern, proc.exe_path, re.IGNORECASE):
                        return True
                    if proc.command_line and re.search(pattern, proc.command_line, re.IGNORECASE):
                        return True
                except re.error:
                    continue
            return False

        elif mode == MatchMode.PATH:
            if not self._ensure_process_path(proc):
                return False
            return self._paths_match(proc.exe_path, rule.app_path)

        elif mode == MatchMode.PATH_CONTAINS:
            for fragment in rule.path_fragments:
                if self._ensure_process_path(proc) and fragment.lower() in proc.exe_path.lower():
                    return True
            return False

        elif mode == MatchMode.COMMAND_LINE:
            if not proc.command_line or not rule.command_keywords:
                return False
            cmd_lower = proc.command_line.lower()
            return any(kw.lower() in cmd_lower for kw in rule.command_keywords)

        elif mode == MatchMode.AUTO:
            return self._auto_match(proc, rule)

        return False

    def _auto_match(self, proc: ProcessInfo, rule: AppRule) -> bool:
        if proc.name_lower in rule.get_all_aliases():
            return True

        if self._ensure_process_path(proc) and self._paths_match(proc.exe_path, rule.app_path):
            return True

        if self._ensure_process_path(proc) and rule.app_path:
            try:
                proc_dir = Path(proc.exe_path).parent
                rule_dir = Path(rule.app_path).parent
                if proc_dir == rule_dir:
                    return True
            except Exception:
                pass

        for pattern in rule.wildcard_patterns:
            if fnmatch.fnmatch(proc.name_lower, pattern.lower()):
                return True
            if self._ensure_process_path(proc) and fnmatch.fnmatch(proc.exe_path.lower(), pattern.lower()):
                return True

        for pattern in rule.regex_patterns:
            try:
                if re.search(pattern, proc.name, re.IGNORECASE):
                    return True
                if self._ensure_process_path(proc) and re.search(pattern, proc.exe_path, re.IGNORECASE):
                    return True
            except re.error:
                continue

        if rule.command_keywords and proc.command_line:
            cmd_lower = proc.command_line.lower()
            for kw in rule.command_keywords:
                if kw.lower() in cmd_lower:
                    return True

        return False

    def _match_by_default(self, app_path: str, exe_name: str,
                          processes: List[ProcessInfo]) -> List[ProcessInfo]:
        results = []
        exe_name_lower = exe_name.lower()
        app_path_lower = app_path.lower()

        for proc in processes:
            if proc.name_lower == exe_name_lower:
                results.append(proc)
                continue

            if self._ensure_process_path(proc) and proc.exe_path.lower() == app_path_lower:
                results.append(proc)
                continue


            if self._ensure_process_path(proc) and app_path:
                try:
                    proc_dir = Path(proc.exe_path).parent
                    app_dir = Path(app_path).parent
                    if proc_dir == app_dir:
                        stem = Path(app_path).stem.lower()
                        if stem in proc.name_lower or proc.name_lower.startswith(stem[:3]):
                            results.append(proc)
                            continue
                except Exception:
                    pass

        return results

    def _auto_discover_aliases(self, app_path: str):
        rule = self._rules.get(app_path)
        if not rule:
            return

        all_processes = self.get_all_running_processes()
        app_dir = Path(app_path).parent
        app_stem = Path(app_path).stem.lower()
        app_name = Path(app_path).name.lower()

        discovered = set()

        for proc in all_processes:
            proc_name_lower = proc.name_lower
            if proc_name_lower == app_name:
                continue

            if app_stem and len(app_stem) >= 3:
                if app_stem in proc_name_lower:
                    discovered.add(proc.name)

            if not (app_stem in proc_name_lower or proc_name_lower.startswith(app_stem[:4])):
                continue

            if self._ensure_process_path(proc):
                try:
                    proc_path = Path(proc.exe_path)
                    proc_dir = proc_path.parent
                    if proc_dir == app_dir:
                        discovered.add(proc.name)
                    elif self._paths_match(proc.exe_path, app_path):
                        discovered.add(proc.name)
                except Exception:
                    pass

        if discovered:
            rule.auto_discovered_aliases.update(discovered)
            self.logger.info(
                f"自动发现 {Path(app_path).name} 的别名: {discovered}"
            )

    def _enumerate_processes(self, name_filter: Optional[Set[str]] = None) -> List[ProcessInfo]:
        if sys.platform != 'win32':
            return self._enumerate_processes_fallback(name_filter)

        processes = []
        try:
            snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snapshot == -1 or snapshot == 0:
                return self._enumerate_processes_fallback(name_filter)

            try:
                entry = PROCESSENTRY32W()
                entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

                if Process32FirstW(snapshot, ctypes.byref(entry)):
                    while True:
                        name = entry.szExeFile
                        if name_filter and name.lower() not in name_filter:
                            if not Process32NextW(snapshot, ctypes.byref(entry)):
                                break
                            continue
                        proc = ProcessInfo(
                            pid=entry.th32ProcessID,
                            name=name,
                            parent_pid=entry.th32ParentProcessID,
                            thread_count=entry.cntThreads,
                        )
                        processes.append(proc)

                        if not Process32NextW(snapshot, ctypes.byref(entry)):
                            break
            finally:
                CloseHandle(snapshot)
        except Exception as e:
            self.logger.error(f"进程枚举失败: {e}")
            return self._enumerate_processes_fallback(name_filter)

        return processes

    def _enumerate_processes_fallback(self, name_filter: Optional[Set[str]] = None) -> List[ProcessInfo]:
        import subprocess
        processes = []
        try:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip().strip('"')
                if not line:
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2:
                    try:
                        name = parts[0]
                        if name_filter and name.lower() not in name_filter:
                            continue
                        proc = ProcessInfo(
                            pid=int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                            name=name,
                        )
                        if proc.pid > 0:
                            processes.append(proc)
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            self.logger.error(f"备用进程枚举失败: {e}")
        return processes

    def _get_process_path(self, pid: int) -> Optional[str]:
        if pid == 0:
            return None

        now = time.time()

        if pid in self._pid_path_cache:
            cache_time, cache_value = self._pid_path_cache[pid]
            if (now - cache_time) < self._pid_path_cache_ttl:
                if cache_value is self._PID_FAILED:
                    return None
                return cache_value

        try:
            h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not h_process:
                self._pid_path_cache[pid] = (now, self._PID_FAILED)
                return None
            try:
                size = DWORD(32768)
                buf = ctypes.create_unicode_buffer(32768)
                if QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                    path = buf.value
                    self._pid_path_cache[pid] = (now, path)
                    return path
                else:
                    self._pid_path_cache[pid] = (now, self._PID_FAILED)
            finally:
                CloseHandle(h_process)
        except Exception:
            self._pid_path_cache[pid] = (now, self._PID_FAILED)
        return None

    def _ensure_process_path(self, proc: ProcessInfo) -> Optional[str]:
        if proc.exe_path is None:
            proc.exe_path = self._get_process_path(proc.pid)
        return proc.exe_path

    def get_process_path(self, pid: int) -> Optional[str]:
        return self._get_process_path(pid)

    def _get_process_command_line(self, pid: int) -> Optional[str]:
        import subprocess
        try:
            result = subprocess.run(
                ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine', '/format:csv'],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 3:
                return lines[2].strip().strip('"')
            if len(lines) == 2:
                return lines[1].strip().strip('"')
        except Exception:
            pass
        return None

    @staticmethod
    def _paths_match(path1: str, path2: str) -> bool:
        try:
            if path1.lower() == path2.lower():
                return True
            return Path(path1).resolve() == Path(path2).resolve()
        except Exception:
            return path1.lower() == path2.lower()

    def _invalidate_cache(self):
        self._cache.clear()
        self._proc_cache.clear()
        self._pid_path_cache.clear()

    def get_running_configured_apps(self) -> Dict[str, List[ProcessInfo]]:
        result = {}
        for app_path in self._rules:
            procs = self._find_app_processes(app_path)
            if procs:
                result[app_path] = procs
        return result

    def match_process_to_any_rule(self, proc: ProcessInfo) -> Optional[str]:
        for app_path, rule in self._rules.items():
            for mode in rule.match_modes:
                if self._match_single(proc, rule, mode):
                    return app_path
        return None

    def refresh_discovery(self, app_path: str = None):
        if app_path:
            self._auto_discover_aliases(app_path)
        else:
            for path in self._rules:
                self._auto_discover_aliases(path)
        self._invalidate_cache()

    def export_rules(self) -> dict:
        return {
            'rules': {path: rule.to_dict() for path, rule in self._rules.items()},
            'version': '1.0',
        }

    def import_rules(self, data: dict):
        rules_data = data.get('rules', {})
        for path, rule_data in rules_data.items():
            self._rules[path] = AppRule.from_dict(rule_data)
        self._invalidate_cache()


_default_detector: Optional[ProcessDetector] = None


def get_detector() -> ProcessDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = ProcessDetector()
    return _default_detector


def is_process_running(exe_path: str, aliases: List[str] = None) -> bool:
    detector = get_detector()
    kwargs = {}
    if aliases:
        kwargs['aliases'] = aliases
    detector.add_app_rule(exe_path, **kwargs)
    return detector.is_app_running(exe_path)


def find_process(exe_path: str, aliases: List[str] = None) -> List[ProcessInfo]:
    detector = get_detector()
    kwargs = {}
    if aliases:
        kwargs['aliases'] = aliases
    detector.add_app_rule(exe_path, **kwargs)
    return detector.get_process_info(exe_path)