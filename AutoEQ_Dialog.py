import sys
import re
import time
import logging
import json
import threading
import pickle
from pathlib import Path

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QMessageBox, QHeaderView,
    QAbstractItemView, QFrame, QScrollArea, QWidget, QMenu, QComboBox
)
from PySide6.QtCore import Signal, QThread, QTimer, QSettings, Qt, QPointF
from PySide6.QtGui import QTextCursor, QDesktopServices, QAction, QPainter, QColor, QPolygonF
from PySide6.QtCore import QUrl

from Graphic_EQualizer import ToggleSwitch
from Translation import tr, on_language_changed


def parse_parametric_to_graphic(content_str):
    preamp = 0.0
    filters = []
    lines = content_str.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        lower = line.lower()
        if lower.startswith('preamp:'):
            parts = line.split()
            for part in parts:
                try:
                    preamp = float(part)
                    break
                except ValueError:
                    continue
        elif lower.startswith('filter '):
            match = re.search(
                r'filter\s+\d+\s*:\s*on\s+\w+\s+fc\s+([\d.]+)\s*hz\s+gain\s+([\d.\-]+)\s*db\s+q\s+([\d.]+)',
                line, re.IGNORECASE
            )
            if match:
                fc = float(match.group(1))
                gain = float(match.group(2))
                q = float(match.group(3))
                filters.append((fc, gain, q))

    if not filters:
        return preamp, {}

    gain_map = {}
    import math

    for fc, gain, q in filters:
        f_low = max(20, fc / 3)
        f_high = min(20000, fc * 3)
        num_points = 12

        log_low = math.log10(f_low)
        log_high = math.log10(f_high)
        for i in range(num_points):
            log_f = log_low + (log_high - log_low) * i / (num_points - 1)
            f = 10 ** log_f
            f = round(f, 1)
            if f > 0 and fc > 0:
                ratio = f / fc
                divisor = 1.0 + (q * (ratio - 1.0 / ratio)) ** 2
                if divisor > 0:
                    response = gain * math.sqrt(1.0 / divisor)
                else:
                    response = 0.0
            else:
                response = 0.0

            existing = gain_map.get(f, 0.0)
            gain_map[f] = existing + response

    for f in list(gain_map.keys()):
        gain_map[f] = round(gain_map[f], 2)

    return preamp, gain_map


class DownloadWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(int, int)
    file_downloaded = Signal(dict)

    def __init__(self, save_root, eq_types=None):
        super().__init__()
        self.logger = logging.getLogger('download').getChild('DownloadWorker')
        self.cache_dir = Path(save_root) / "cache"
        self.data_dir = Path(save_root) / "EQ"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.eq_types = eq_types if eq_types else ["GraphicEQ", "ParametricEQ", "FixedBandEQ"]
        self.eq_pkl_paths = {}
        for et in self.eq_types:
            self.eq_pkl_paths[et] = self.data_dir / f"{et}.pkl"

        self._total_files = 0
        self._completed = 0
        self._success = 0
        self._failed = 0
        self._abort_event = threading.Event()
        self._lock = threading.Lock()

    @staticmethod
    def _sanitize(name):
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        return name.strip().rstrip('.')

    @staticmethod
    def _fix_escaped_name(name):
        if not isinstance(name, str):
            return name
        pattern_oct = r'\\([0-7]{3})'

        def repl_oct(match):
            oct_str = match.group(1)
            return chr(int(oct_str, 8))

        fixed = re.sub(pattern_oct, repl_oct, name)
        try:
            fixed = fixed.encode('latin-1').decode('utf-8')
        except UnicodeError:
            pass
        fixed = fixed.strip('"\'')
        return fixed

    def _make_file_info(self, source, htype, model, eq_key=None, eq_type="GraphicEQ"):
        source_clean = DownloadWorker._sanitize(source)
        htype_clean = DownloadWorker._sanitize(htype)
        model_clean = DownloadWorker._sanitize(model)
        if eq_key is None:
            eq_key = f"{source_clean}/{htype_clean}/{model_clean}"
        return {
            'display': model,
            'measurer': source,
            'method': htype,
            'brand': source,
            'model': model,
            'measurement': htype,
            'eq_key': eq_key,
            'eq_type': eq_type
        }

    def run(self):
        import zipfile
        import urllib.request
        import ssl

        ZIP_URL = "https://codeload.github.com/jaakkopasanen/AutoEq/zip/refs/heads/master"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        self.log.emit(tr("msg_downloading"))
        zip_path = self.cache_dir / "autoeq_master.zip"

        max_retries = 5
        response = None
        for retry in range(max_retries):
            if self._abort_event.is_set():
                self.log.emit(tr("msg_user_abort"))
                self.finished.emit(0, 0)
                return
            try:
                self.log.emit(tr("msg_connecting_github", retry=retry+1, max=max_retries))
                req = urllib.request.Request(ZIP_URL, headers=headers)
                response = urllib.request.urlopen(req, timeout=30, context=ssl_context)
                break
            except Exception as e:
                if retry == max_retries - 1:
                    self.logger.exception("下载 zip 失败")
                    self.log.emit(tr("msg_download_failed", error=str(e)))
                    self.finished.emit(0, 0)
                    return
                self.logger.warning(f"网络波动，自动重试 {retry+1}/{max_retries}")
                self.log.emit(tr("msg_network_retry", retry=retry+1, max=max_retries))
                time.sleep(2)

        self.log.emit(tr("msg_downloading_data"))
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        chunk_size = 1024 * 1024

        with open(zip_path, 'wb') as f:
            for chunk in iter(lambda: response.read(chunk_size), b''):
                if self._abort_event.is_set():
                    try:
                        zip_path.unlink()
                    except Exception:
                        pass
                    self.log.emit(tr("msg_download_aborted"))
                    self.finished.emit(0, 0)
                    return
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = min(int((downloaded / total_size) * 100), 100)
                        self.progress.emit(progress, 100)

        self.log.emit(tr("msg_parsing_zip"))

        eq_keywords = {
            "GraphicEQ": ["graphiceq", "graphic eq", "graphic_eq", "graphic-eq"],
            "ParametricEQ": ["parametriceq", "parametric eq", "parametric_eq", "parametric-eq"],
            "FixedBandEQ": ["fixedbandeq", "fixed band eq", "fixed_band_eq", "fixed-band-eq"],
        }

        entries_info = []

        try:
            with zipfile.ZipFile(zip_path) as zf:
                all_entries = zf.namelist()
                for entry in all_entries:
                    if self._abort_event.is_set():
                        self.finished.emit(self._success, self._failed)
                        return
                    if not entry.startswith("AutoEq-master/results/"):
                        continue
                    if not entry.lower().endswith(".txt"):
                        continue
                    filename_lower = entry.rsplit("/", 1)[-1].lower()
                    orig_filename = entry.rsplit("/", 1)[-1]
                    for eq_type, keywords in eq_keywords.items():
                        if any(kw in filename_lower for kw in keywords):
                            parts = entry.split("/")
                            if len(parts) >= 4:
                                source = parts[2]
                                htype = parts[3] if len(parts) >= 5 else ""
                                name_no_ext = orig_filename
                                if name_no_ext.lower().endswith(".txt"):
                                    name_no_ext = name_no_ext[:-4]
                                for kw in keywords:
                                    pattern = re.compile(re.escape(kw), re.IGNORECASE)
                                    name_no_ext = pattern.sub("", name_no_ext)
                                name_no_ext = re.sub(r'[\(\)\[\]]', '', name_no_ext)
                                model = name_no_ext.strip().rstrip(" -_,").strip()
                                entries_info.append((source, htype, model, entry, eq_type))
                            break
        except Exception as e:
            self.logger.exception("解析 ZIP 文件失败")
            self.log.emit(tr("msg_parse_zip_failed", error=str(e)))
            try:
                zip_path.unlink()
            except Exception:
                pass
            self.finished.emit(0, 0)
            return

        self._total_files = len(entries_info)
        type_counts = {}
        for _, _, _, _, et in entries_info:
            type_counts[et] = type_counts.get(et, 0) + 1
        self.logger.info(f"ZIP 原始匹配: {type_counts}")
        self.log.emit(f"ZIP 匹配: GraphicEQ={type_counts.get('GraphicEQ',0)}, ParametricEQ={type_counts.get('ParametricEQ',0)}, FixedBandEQ={type_counts.get('FixedBandEQ',0)}")
        self.progress.emit(0, self._total_files)
        self.logger.info(f"共 {self._total_files} 个文件待处理（三种EQ类型）")
        self.log.emit(tr("msg_parse_complete", total=self._total_files))

        if self._total_files == 0:
            self.log.emit(tr("msg_no_downloadable_files"))
            self.finished.emit(0, 0)
            return

        eq_data_graphic = {}
        eq_data_parametric = {}
        eq_data_fixed_band = {}
        eq_data_by_type = {
            "GraphicEQ": eq_data_graphic,
            "ParametricEQ": eq_data_parametric,
            "FixedBandEQ": eq_data_fixed_band,
        }
        path_lookup = {t: {} for t in eq_data_by_type}

        zip_name_set = set()
        with zipfile.ZipFile(zip_path) as zf:
            zip_name_set = set(zf.namelist())

        with zipfile.ZipFile(zip_path) as zf:
            for i, (source, htype, model, zip_entry, eq_type) in enumerate(entries_info):
                if self._abort_event.is_set():
                    break

                source_fixed = DownloadWorker._fix_escaped_name(source)
                htype_fixed = DownloadWorker._fix_escaped_name(htype)
                model_fixed = DownloadWorker._fix_escaped_name(model)

                source_clean = DownloadWorker._sanitize(source_fixed)
                htype_clean = DownloadWorker._sanitize(htype_fixed)
                model_clean = DownloadWorker._sanitize(model_fixed)
                eq_key = f"{source_clean}/{htype_clean}/{model_clean}"

                if eq_key in eq_data_by_type[eq_type]:
                    self.logger.warning(
                        f"[{eq_type}] eq_key 碰撞！key={eq_key}, "
                        f"覆盖条目={zip_entry}, 原有条目被替换"
                    )

                try:
                    zip_content = zf.read(zip_entry)
                except Exception as exc:
                    self.logger.warning(f"读取 zip 条目失败: {zip_entry}: {exc}")
                    self.log.emit(tr("msg_zip_entry_read_failed", entry=zip_entry, error=str(exc)))
                    with self._lock:
                        self._failed += 1
                        self._completed += 1
                    self.progress.emit(self._completed, self._total_files)
                    continue

                try:
                    eq_data_by_type[eq_type][eq_key] = zip_content.decode('utf-8')
                except UnicodeDecodeError:
                    self.logger.warning(f"UTF-8 解码失败，尝试 latin-1: {zip_entry}")
                    self.log.emit(tr("msg_decode_fallback", entry=zip_entry))
                    eq_data_by_type[eq_type][eq_key] = zip_content.decode('latin-1')

                info = self._make_file_info(source_fixed, htype_fixed, model_fixed, eq_key, eq_type)
                self.file_downloaded.emit(info)
                path_lookup[eq_type][eq_key] = (info, zip_entry)
                with self._lock:
                    self._completed += 1
                    self._success += 1
                self.progress.emit(self._completed, self._total_files)

        all_types = list(eq_data_by_type.keys())
        counts = {t: len(eq_data_by_type[t]) for t in all_types}
        baseline_type = max(counts, key=counts.get)
        self.logger.info(f"补提取基准类型: {baseline_type} ({counts[baseline_type]} 条)")
        self.log.emit(f"补提取基准: {baseline_type}={counts[baseline_type]} 条")

        eq_name_maps = {
            "GraphicEQ": ["GraphicEQ", "Graphic EQ", "Graphic_EQ", "Graphic-EQ"],
            "ParametricEQ": ["ParametricEQ", "Parametric EQ", "Parametric_EQ", "Parametric-EQ"],
            "FixedBandEQ": ["FixedBandEQ", "Fixed Band EQ", "Fixed_Band_EQ", "Fixed-Band-EQ"],
        }

        patched = 0
        with zipfile.ZipFile(zip_path) as zf:
            for eq_key, (base_info, base_zip_entry) in path_lookup[baseline_type].items():
                for other_type in all_types:
                    if other_type == baseline_type:
                        continue
                    if eq_key in path_lookup[other_type]:
                        continue

                    dir_part = base_zip_entry.rsplit("/", 1)[0]
                    filename = base_zip_entry.rsplit("/", 1)[-1]

                    found = False
                    for base_kw in eq_name_maps[baseline_type]:
                        if not found:
                            for other_kw in eq_name_maps[other_type]:
                                candidate_filename = filename.replace(base_kw, other_kw)
                                if candidate_filename == filename:
                                    continue
                                candidate_path = f"{dir_part}/{candidate_filename}"
                                if candidate_path in zip_name_set:
                                    try:
                                        content = zf.read(candidate_path).decode('utf-8')
                                    except UnicodeDecodeError:
                                        content = zf.read(candidate_path).decode('latin-1')
                                    except Exception:
                                        continue

                                    eq_data_by_type[other_type][eq_key] = content
                                    info = self._make_file_info(
                                        base_info['measurer'], base_info['method'],
                                        base_info['model'], eq_key, other_type
                                    )
                                    self.file_downloaded.emit(info)
                                    path_lookup[other_type][eq_key] = (info, candidate_path)
                                    with self._lock:
                                        self._success += 1
                                    self._completed += 1
                                    self.progress.emit(self._completed, self._total_files)
                                    found = True
                                    patched += 1
                                    self.logger.info(f"补提取: [{other_type}] {eq_key} <- {candidate_path}")
                                    break

        if patched > 0:
            self.logger.info(f"补提取完成，共补全 {patched} 条缺失的 EQ 条目")
            self.log.emit(f"补提取: 已补全 {patched} 条缺失的 EQ 条目")
        else:
            self.logger.info("无需补提取，所有 EQ 类型条目数一致")

        for eq_type, eq_data in eq_data_by_type.items():
            pkl_path = self.eq_pkl_paths[eq_type]
            self.log.emit(tr("msg_saving_eq_data", name=pkl_path.name))
            try:
                with open(pkl_path, 'wb') as f:
                    pickle.dump(eq_data, f, protocol=pickle.HIGHEST_PROTOCOL)
                self.logger.info(f"{eq_type}.pkl 已保存，包含 {len(eq_data)} 条 EQ 数据")
            except Exception as e:
                self.logger.exception(f"保存 {eq_type}.pkl 失败")
                self.log.emit(tr("msg_save_pkl_failed", error=str(e)))

        try:
            zip_path.unlink()
        except Exception:
            pass

        try:
            response.close()
        except Exception:
            pass

        total_eq = sum(len(d) for d in eq_data_by_type.values())
        self.log.emit(
            tr("msg_update_complete", success=self._success, failed=self._failed, total=total_eq)
        )
        self.finished.emit(self._success, self._failed)
        self.logger.info(
            f"下载完成，成功: {self._success}, 失败: {self._failed}"
        )

    def requestInterruption(self):
        super().requestInterruption()
        self._abort_event.set()
        self.logger.info("下载线程收到中断请求")


class DirScanWorker(QThread):
    finished = Signal(list)
    progress = Signal(int, int)
    log = Signal(str)

    def __init__(self, dir_path, eq_pkl_paths=None):
        super().__init__()
        self.dir_path = dir_path
        self.eq_pkl_paths = eq_pkl_paths if eq_pkl_paths else {}

    @staticmethod
    def _sanitize(name):
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        return name.strip().rstrip('.')

    def run(self):
        items = []
        eq_data_all = {
            "GraphicEQ": {},
            "ParametricEQ": {},
            "FixedBandEQ": {},
        }
        root = Path(self.dir_path)

        eq_keywords = {
            "GraphicEQ": ["graphiceq", "graphic eq", "graphic_eq", "graphic-eq"],
            "ParametricEQ": ["parametriceq", "parametric eq", "parametric_eq", "parametric-eq"],
            "FixedBandEQ": ["fixedbandeq", "fixed band eq", "fixed_band_eq", "fixed-band-eq"],
        }

        all_files = []
        try:
            for fp in root.rglob("*.txt"):
                filename = fp.name.lower()
                for eq_type, keywords in eq_keywords.items():
                    if any(kw in filename for kw in keywords):
                        all_files.append((fp, eq_type))
                        break
        except Exception as e:
            self.logger.exception("目录扫描失败")
            self.log.emit(tr("msg_dir_scan_failed", error=str(e)))

        total = len(all_files)
        for idx, (txt_path, eq_type) in enumerate(all_files):
            if self.isInterruptionRequested():
                return
            try:
                rel_path = txt_path.relative_to(root)
                parts = list(rel_path.parts)
                if len(parts) >= 4 and parts[0].lower() == 'results':
                    parts = parts[1:]
                if len(parts) >= 3:
                    source = DownloadWorker._fix_escaped_name(parts[0])
                    htype = DownloadWorker._fix_escaped_name(parts[1])
                    model_raw = parts[-1]
                    if model_raw.lower().endswith(".txt"):
                        model_raw = model_raw[:-4]
                    keywords = eq_keywords.get(eq_type, [])
                    for kw in keywords:
                        pattern = re.compile(re.escape(kw), re.IGNORECASE)
                        model_raw = pattern.sub("", model_raw)
                    model_raw = re.sub(r'[\(\)\[\]]', '', model_raw)
                    model_raw = model_raw.strip().rstrip(" -_,").strip()
                    model = DownloadWorker._fix_escaped_name(model_raw)
                    source_clean = self._sanitize(source)
                    htype_clean = self._sanitize(htype)
                    model_clean = self._sanitize(model)
                    eq_key = f"{source_clean}/{htype_clean}/{model_clean}"

                    items.append({
                        'display': model,
                        'measurer': source,
                        'method': htype,
                        'brand': source,
                        'model': model,
                        'measurement': htype,
                        'local_path': str(txt_path),
                        'eq_key': eq_key,
                        'eq_type': eq_type
                    })

                    if eq_type in eq_data_all:
                        try:
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                eq_data_all[eq_type][eq_key] = f.read()
                        except UnicodeDecodeError:
                            with open(txt_path, 'r', encoding='latin-1') as f:
                                eq_data_all[eq_type][eq_key] = f.read()
                else:
                    measurer = parts[0] if len(parts) >= 1 else ""
                    htype = parts[1] if len(parts) >= 2 else ""
                    model = parts[2] if len(parts) >= 3 else ""
                    items.append({
                        'display': model,
                        'measurer': measurer,
                        'method': htype,
                        'brand': measurer,
                        'model': model,
                        'measurement': htype,
                        'local_path': str(txt_path),
                        'eq_type': eq_type
                    })
            except Exception as e:
                self.logger.exception(f"处理文件失败: {txt_path}")
                self.log.emit(tr("msg_dir_entry_failed", file=str(txt_path), error=str(e)))
            self.progress.emit(idx + 1, total)

        for eq_type in eq_data_all:
            if self.eq_pkl_paths and eq_type in self.eq_pkl_paths and eq_data_all[eq_type]:
                pkl_path = self.eq_pkl_paths[eq_type]
                try:
                    eq_dir = Path(pkl_path).parent
                    eq_dir.mkdir(parents=True, exist_ok=True)
                    with open(pkl_path, 'wb') as f:
                        pickle.dump(eq_data_all[eq_type], f, protocol=pickle.HIGHEST_PROTOCOL)
                    self.log.emit(tr("label_graphic_eq_pkl_saved", count=len(eq_data_all[eq_type])))
                except Exception as e:
                    self.log.emit(tr("msg_save_pkl_failed", error=str(e)))

        self.finished.emit(items)


class ScanWorker(QThread):
    finished = Signal(list)
    progress = Signal(int, int)

    def __init__(self, eq_pkl_path, eq_type="GraphicEQ"):
        super().__init__()
        self.eq_pkl_path = eq_pkl_path
        self.eq_type = eq_type

    def run(self):
        items = []
        if not Path(self.eq_pkl_path).exists():
            self.finished.emit([])
            return
        try:
            with open(self.eq_pkl_path, 'rb') as f:
                eq_data = pickle.load(f)
        except Exception:
            self.finished.emit([])
            return

        keys = list(eq_data.keys())
        total = len(keys)
        for idx, eq_key in enumerate(keys):
            if self.isInterruptionRequested():
                return
            parts = eq_key.split('/')
            if len(parts) >= 3:
                source = parts[0]
                htype = parts[1]
                model = '/'.join(parts[2:])
                items.append({
                    'display': model,
                    'measurer': source,
                    'method': htype,
                    'brand': source,
                    'model': model,
                    'measurement': htype,
                    'eq_key': eq_key,
                    'eq_type': self.eq_type
                })
            self.progress.emit(idx + 1, total)
        self.finished.emit(items)


from auto_config_switch import get_settings_path


class DownwardComboBox(QComboBox):
    def showPopup(self):
        super().showPopup()
        container = self.view().window()
        pos = self.mapToGlobal(self.rect().bottomLeft())
        container.move(pos)

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


class AutoEQDialog(QDialog):
    dataReady = Signal(float, str, str, str)

    def __init__(self, parent=None, app_path=None):
        super().__init__(parent)
        self.logger = logging.getLogger(f"{__name__}.AutoEQDialog")
        self.download_logger = logging.getLogger('download').getChild('AutoEQDialog')

        self._app_path = app_path
        self._app_name = self._resolve_app_name(app_path)

        title = tr("dialog_auto_eq_title")
        self.setWindowTitle(title)
        self.resize(900, 600)
        self.setModal(True)

        try:
            from PySide6.QtGui import QIcon
            icon_path = APP_DIR / "EQAPO_Editor.ico"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            self.logger.error(f"设置窗口图标时出错: {e}")

        self.main_window = parent

        self.settings = QSettings(get_settings_path(), QSettings.IniFormat)
        self.local_data_dir = self.settings.value("auto_eq_local_dir", "")
        self.last_selected_path = self._get_last_selected()
        self.show_download_log = self.settings.value("auto_eq_show_download_log", False, type=bool)
        if not self.show_download_log:
            self._set_download_log_level(False)
        self.use_folder_loading = self.settings.value("auto_eq_use_folder_loading", False, type=bool)
        self.search_col_display = self.settings.value("auto_eq_search_display", True, type=bool)
        self.search_col_measurer = self.settings.value("auto_eq_search_measurer", True, type=bool)
        self.search_col_method = self.settings.value("auto_eq_search_method", True, type=bool)

        eq_type_str = self.settings.value("auto_eq_type", "GraphicEQ")
        self._current_eq_type = eq_type_str if eq_type_str in ("GraphicEQ", "ParametricEQ", "FixedBandEQ") else "GraphicEQ"

        self.all_items = []
        self._displayed_indices = []
        self.download_worker = None
        self.scan_worker = None
        self._loading = False

        cache_dir = APP_DIR / "AutoEqData" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        eq_dir = APP_DIR / "AutoEqData" / "EQ"
        eq_dir.mkdir(parents=True, exist_ok=True)
        self.scan_cache_path = cache_dir / "scan_cache.pkl"

        self.eq_pkl_paths = {
            "GraphicEQ": eq_dir / "GraphicEQ.pkl",
            "ParametricEQ": eq_dir / "ParametricEQ.pkl",
            "FixedBandEQ": eq_dir / "FixedBandEQ.pkl",
        }
        self.eq_pkl_path = self.eq_pkl_paths["GraphicEQ"]
        self.cache_max_age = 7 * 24 * 3600

        self._eq_raw_contents = {}

        self._pending_files = []
        self._batch_timer = QTimer()
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._process_pending_files)
        self._batch_interval = 50
        self._existing_keys = set()
        self._download_in_progress = False

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        search_layout = QHBoxLayout()
        self.search_label = QLabel(tr("label_search"))
        search_layout.addWidget(self.search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setFrame(False)
        self.search_edit.setPlaceholderText(tr("placeholder_search"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.search_edit.customContextMenuRequested.connect(self._on_search_context_menu)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        self.search_edit.textChanged.connect(self._on_search_input)
        search_layout.addWidget(self.search_edit)

        self.settings_btn = QPushButton(tr("btn_settings"))
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        self.settings_btn.setAutoDefault(False)
        search_layout.addWidget(self.settings_btn)

        self.eq_type_combo = DownwardComboBox()
        self.eq_type_combo.addItems([
            tr("eq_type_graphic"),
            tr("eq_type_parametric"),
            tr("eq_type_fixed_band"),
        ])
        eq_type_index_map = {"GraphicEQ": 0, "ParametricEQ": 1, "FixedBandEQ": 2}
        self.eq_type_combo.setCurrentIndex(eq_type_index_map.get(self._current_eq_type, 0))
        self.eq_type_combo.currentIndexChanged.connect(self._on_eq_type_changed)
        search_layout.addWidget(self.eq_type_combo)

        self.auto_eq_url_btn = QPushButton(tr("btn_auto_eq_url"))
        self.auto_eq_url_btn.clicked.connect(self._open_auto_eq_url)
        search_layout.addWidget(self.auto_eq_url_btn)

        layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setStyleSheet("QTableWidget { border: 1px solid #444; }")
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([tr("col_headphone"), tr("col_measurer"), tr("col_method")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setAlternatingRowColors(True)
        self.table.setAutoScroll(False)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.manual_import_btn = QPushButton(tr("btn_browse_local_repo"))
        self.manual_import_btn.clicked.connect(self._manual_import)
        button_layout.addWidget(self.manual_import_btn)

        self.update_repo_btn = QPushButton(tr("btn_update_local_repo"))
        self.update_repo_btn.clicked.connect(self._update_local_repo)
        button_layout.addWidget(self.update_repo_btn)

        self.refresh_cache_btn = QPushButton(tr("btn_refresh_cache"))
        self.refresh_cache_btn.clicked.connect(self._refresh_cache)
        button_layout.addWidget(self.refresh_cache_btn)

        button_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedWidth(200)
        button_layout.addWidget(self.progress_bar)

        self.cancel_download_btn = QPushButton(tr("btn_cancel_download"))
        self.cancel_download_btn.setVisible(False)
        self.cancel_download_btn.clicked.connect(self._cancel_download)
        button_layout.addWidget(self.cancel_download_btn)

        button_layout.addStretch()

        self.ok_button = QPushButton(tr("btn_use"))
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self._download_selected)
        self.ok_button.setAutoDefault(True)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton(tr("btn_cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.log_text = QTextEdit()
        self.log_text.setStyleSheet("QTextEdit { border: 1px solid #444; }")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setVisible(False)
        layout.addWidget(self.log_text)

        self._load_last_directory_async()

        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        self.repaint()

        self.center_on_screen()

        on_language_changed(self._retranslate_ui)

    @staticmethod
    def _natural_key(s):
        import re
        return [int(part) if part.isdigit() else part.lower()
                for part in re.split(r'(\d+)', s)]

    def _retranslate_ui(self):
        title = tr("dialog_auto_eq_title")
        self.setWindowTitle(title)
        self.search_label.setText(tr("label_search"))
        self.search_edit.setPlaceholderText(tr("placeholder_search"))
        self.settings_btn.setText(tr("btn_settings"))
        self.eq_type_combo.setItemText(0, tr("eq_type_graphic"))
        self.eq_type_combo.setItemText(1, tr("eq_type_parametric"))
        self.eq_type_combo.setItemText(2, tr("eq_type_fixed_band"))
        self.auto_eq_url_btn.setText(tr("btn_auto_eq_url"))
        self.table.setHorizontalHeaderLabels([tr("col_headphone"), tr("col_measurer"), tr("col_method")])
        self.manual_import_btn.setText(tr("btn_browse_local_repo"))
        self.update_repo_btn.setText(tr("btn_update_local_repo"))
        self.refresh_cache_btn.setText(tr("btn_refresh_cache"))
        self.cancel_download_btn.setText(tr("btn_cancel_download"))
        self.ok_button.setText(tr("btn_use"))
        self.cancel_button.setText(tr("btn_cancel"))

    def center_on_screen(self):
        screen = self.screen()
        if screen is None:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            self.move(geometry.center() - self.rect().center())

    @staticmethod
    def _resolve_app_name(app_path):
        if not app_path:
            return None
        from app_config_manager import RESIDENT_KEY
        if app_path == RESIDENT_KEY:
            return "EQAPO编辑器"
        try:
            return Path(app_path).stem
        except Exception:
            return None

    def _get_last_selected_key(self):
        if self._app_path:
            return f"auto_eq_last_selected_{self._app_path}"
        return "auto_eq_last_selected"

    def _get_last_selected(self):
        key = self._get_last_selected_key()
        return self.settings.value(key, "")

    def _set_last_selected(self, value):
        key = self._get_last_selected_key()
        self.settings.setValue(key, value)

    def _restore_last_selected(self):
        last_selected = self._get_last_selected()
        if not last_selected or not self._displayed_indices:
            return
        for row, idx in enumerate(self._displayed_indices):
            if idx < len(self.all_items):
                item = self.all_items[idx]
                if (item.get('local_path') == last_selected or
                        item.get('eq_key') == last_selected):
                    self.table.selectRow(row)
                    self.table.scrollToItem(
                        self.table.item(row, 0),
                        QAbstractItemView.PositionAtCenter
                    )
                    break

    def _on_eq_type_changed(self, index):
        eq_type_map = {0: "GraphicEQ", 1: "ParametricEQ", 2: "FixedBandEQ"}
        eq_type = eq_type_map.get(index, "GraphicEQ")
        self._current_eq_type = eq_type
        self.settings.setValue("auto_eq_type", eq_type)
        self.settings.sync()
        self._reload_by_eq_type()

    def _reload_by_eq_type(self):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.requestInterruption()
            self.scan_worker.wait(2000)
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.download_worker.wait(2000)

        self.table.setRowCount(0)
        self.all_items.clear()
        self._displayed_indices.clear()
        self._existing_keys.clear()
        self.ok_button.setEnabled(False)

        eq_type = self._current_eq_type
        pkl_path = self.eq_pkl_paths.get(eq_type)

        if pkl_path and pkl_path.exists():
            self.logger.info(f"从 {pkl_path.name} 加载 {eq_type} 数据")
            self._start_scan_for_type(eq_type)
            return

        if self.local_data_dir and Path(self.local_data_dir).is_dir():
            self._start_dir_scan()

    def _reload_table_display(self):
        eq_type = self._current_eq_type
        filtered_items = [item for item in self.all_items if item.get('eq_type') == eq_type]
        indices = [idx for idx, item in enumerate(self.all_items) if item.get('eq_type') == eq_type]
        self._populate_table_from(filtered_items, indices)
        self._existing_keys.clear()
        for item in filtered_items:
            key = (item['display'], item['measurer'], item['method'], item.get('eq_type', ''))
            self._existing_keys.add(key)
        QTimer.singleShot(0, self._restore_last_selected)

    def _start_scan_for_type(self, eq_type):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.requestInterruption()
            self.scan_worker.wait(2000)

        self._pending_files.clear()
        self._batch_timer.stop()

        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem(tr("msg_scanning")))
        self.ok_button.setEnabled(False)

        pkl_path = self.eq_pkl_paths.get(eq_type)
        self.scan_worker = ScanWorker(pkl_path, eq_type)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.start()

    def _load_last_directory_async(self):
        eq_type = self._current_eq_type

        if self.scan_cache_path and self.scan_cache_path.exists():
            try:
                mtime = self.scan_cache_path.stat().st_mtime
                if time.time() - mtime < self.cache_max_age:
                    with open(self.scan_cache_path, 'rb') as f:
                        data = pickle.load(f)
                    if isinstance(data, list):
                        self.logger.info("检测到旧版缓存格式（列表），将重新加载")
                        self._start_dir_scan()
                        return
                    if data.get('items'):
                        self.all_items = data.get('items', [])
                        has_current = any(it.get('eq_type') == eq_type for it in self.all_items)
                        if has_current:
                            self.logger.info(f"从缓存加载结果: {len(self.all_items)} 项（全部类型），当前显示: {eq_type}")
                            self._reload_table_display()
                            return
            except Exception as e:
                self.logger.warning(f"读取缓存失败，将重新加载: {e}")

        pkl_path = self.eq_pkl_paths.get(eq_type)
        if pkl_path and pkl_path.exists():
            self._start_scan_for_type(eq_type)
            return

        if self.local_data_dir and Path(self.local_data_dir).is_dir():
            self._start_dir_scan()

    def _start_scan(self):
        self._pending_files.clear()
        self._batch_timer.stop()

        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem(tr("msg_scanning")))
        self.ok_button.setEnabled(False)

        eq_type = self._current_eq_type
        pkl_path = self.eq_pkl_paths.get(eq_type, self.eq_pkl_path)
        self.scan_worker = ScanWorker(pkl_path, eq_type)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.start()

    def _start_dir_scan(self):
        self._pending_files.clear()
        self._batch_timer.stop()

        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem(tr("msg_scanning")))
        self.ok_button.setEnabled(False)

        self.scan_worker = DirScanWorker(self.local_data_dir, eq_pkl_paths=self.eq_pkl_paths)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.log.connect(self._on_download_log)
        self.scan_worker.start()

    def _on_scan_progress(self, current, total):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

    def _on_scan_finished(self, items):
        existing_eq_keys = {(it.get('eq_key'), it.get('eq_type')) for it in self.all_items if it.get('eq_key')}
        for item in items:
            key = (item.get('eq_key'), item.get('eq_type'))
            if key not in existing_eq_keys:
                existing_eq_keys.add(key)
                self.all_items.append(item)

        self.all_items.sort(key=lambda x: self._natural_key(x['display']))
        self._reload_table_display()
        self._save_cache(self.all_items, self.local_data_dir)
        self.progress_bar.setVisible(False)
        if self.scan_worker:
            self.scan_worker.deleteLater()
            self.scan_worker = None

    def _save_cache(self, items, directory):
        if self.scan_cache_path:
            try:
                data = {
                    'directory': directory,
                    'items': items,
                    'timestamp': time.time(),
                    'eq_type': self._current_eq_type
                }
                with open(self.scan_cache_path, 'wb') as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                self.logger.info(f"扫描结果已缓存，目录: {directory}")
            except Exception as e:
                self.logger.error(f"保存缓存失败: {e}")

    def _populate_table_all(self):
        eq_type = self._current_eq_type
        filtered = [item for item in self.all_items if item.get('eq_type') == eq_type]
        indices = [idx for idx, item in enumerate(self.all_items) if item.get('eq_type') == eq_type]
        self._populate_table_from(filtered, indices)
        self._existing_keys.clear()
        for item in filtered:
            key = (item['display'], item['measurer'], item['method'], item.get('eq_type', ''))
            self._existing_keys.add(key)
        QTimer.singleShot(0, self._restore_last_selected)

    def _populate_table_from(self, items, displayed_indices):
        self._displayed_indices = list(displayed_indices)
        self.table.setUpdatesEnabled(False)
        self.table.clearSelection()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item['display']))
            self.table.setItem(row, 1, QTableWidgetItem(item['measurer']))
            self.table.setItem(row, 2, QTableWidgetItem(item['method']))
        self.table.setUpdatesEnabled(True)
        self.ok_button.setEnabled(self.table.rowCount() > 0)

    def _manual_import(self):
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.requestInterruption()
            self.scan_worker.wait(2000)
        from PySide6.QtWidgets import QFileDialog

        if self.use_folder_loading:
            dir_path = QFileDialog.getExistingDirectory(
                self,
                tr("dialog_select_repo_root"),
                self.local_data_dir if self.local_data_dir else str(Path.home().anchor)
            )
            if not dir_path:
                return
            self.local_data_dir = dir_path
            self.settings.setValue("auto_eq_local_dir", dir_path)
            if self.scan_cache_path and self.scan_cache_path.exists():
                self.scan_cache_path.unlink()
            for p in self.eq_pkl_paths.values():
                if p.exists():
                    p.unlink()
            self._load_last_directory_async()
        else:
            zip_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("dialog_select_zip"),
                self.local_data_dir if self.local_data_dir else str(Path.home().anchor),
                tr("file_filter_zip")
            )
            if not zip_path:
                return
            self._extract_eq_from_zip(zip_path)

    def _extract_eq_from_zip(self, zip_path):
        import zipfile
        from pathlib import Path as PathLib

        self.log_text.setVisible(self.show_download_log)
        self.log_text.clear()
        self.log_text.append(tr("msg_parsing_zip_file", name=PathLib(zip_path).name))
        self.download_logger.info(f"开始从压缩包提取EQ数据: {zip_path}")

        eq_data_by_type = {
            "GraphicEQ": {},
            "ParametricEQ": {},
            "FixedBandEQ": {},
        }
        items = []
        total = 0
        success = 0
        failed = 0

        eq_keywords = {
            "GraphicEQ": ["graphiceq", "graphic eq", "graphic_eq", "graphic-eq"],
            "ParametricEQ": ["parametriceq", "parametric eq", "parametric_eq", "parametric-eq"],
            "FixedBandEQ": ["fixedbandeq", "fixed band eq", "fixed_band_eq", "fixed-band-eq"],
        }

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                all_entries = zf.namelist()
                eq_entries = []

                for entry in all_entries:
                    if not entry.lower().endswith(".txt"):
                        continue
                    filename = entry.rsplit("/", 1)[-1].lower()
                    for eq_type, keywords in eq_keywords.items():
                        if any(kw in filename for kw in keywords):
                            parts = entry.split("/")
                            if len(parts) >= 1 and parts[0].lower() == 'results':
                                parts = parts[1:]
                            elif len(parts) >= 2 and parts[0].startswith("AutoEq") and parts[1].lower() == 'results':
                                parts = parts[2:]
                            eq_entries.append((entry, parts, eq_type))
                            break

                total = len(eq_entries)
                type_counts = {}
                for _, _, et in eq_entries:
                    type_counts[et] = type_counts.get(et, 0) + 1
                self.log_text.append(f"ZIP 匹配: GraphicEQ={type_counts.get('GraphicEQ',0)}, ParametricEQ={type_counts.get('ParametricEQ',0)}, FixedBandEQ={type_counts.get('FixedBandEQ',0)}")
                self.download_logger.info(f"ZIP 原始匹配({PathLib(zip_path).name}): {type_counts}")
                self.log_text.append(tr("msg_found_graphic_eq", total=total))

                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(0)

                path_lookup = {t: {} for t in eq_data_by_type}
                zip_name_set = set(all_entries)

                for idx, (entry_path, parts, eq_type) in enumerate(eq_entries):
                    if len(parts) >= 3:
                        source = DownloadWorker._fix_escaped_name(parts[0])
                        htype = DownloadWorker._fix_escaped_name(parts[1]) if len(parts) >= 4 else ""
                        orig_filename = entry_path.rsplit("/", 1)[-1]
                        keywords = eq_keywords.get(eq_type, [])
                        name_no_ext = orig_filename
                        if name_no_ext.lower().endswith(".txt"):
                            name_no_ext = name_no_ext[:-4]
                        for kw in keywords:
                            pattern = re.compile(re.escape(kw), re.IGNORECASE)
                            name_no_ext = pattern.sub("", name_no_ext)
                        name_no_ext = re.sub(r'[\(\)\[\]]', '', name_no_ext)
                        model_raw = name_no_ext.strip().rstrip(" -_,").strip()
                        model = DownloadWorker._fix_escaped_name(model_raw)

                        source_clean = DownloadWorker._sanitize(source)
                        htype_clean = DownloadWorker._sanitize(htype)
                        model_clean = DownloadWorker._sanitize(model)
                        eq_key = f"{source_clean}/{htype_clean}/{model_clean}"

                        if eq_key in eq_data_by_type[eq_type]:
                            self.download_logger.warning(
                                f"[{eq_type}] eq_key 碰撞！key={eq_key}, "
                                f"覆盖条目={entry_path}"
                            )

                        try:
                            content_bytes = zf.read(entry_path)
                            try:
                                content = content_bytes.decode('utf-8')
                            except UnicodeDecodeError:
                                content = content_bytes.decode('latin-1')

                            eq_data_by_type[eq_type][eq_key] = content
                            items.append({
                                'display': model,
                                'measurer': source,
                                'method': htype,
                                'brand': source,
                                'model': model,
                                'measurement': htype,
                                'eq_key': eq_key,
                                'eq_type': eq_type
                            })
                            self._eq_raw_contents[eq_key] = content
                            success += 1
                            path_lookup[eq_type][eq_key] = (entry_path, source, htype, model)
                        except Exception as e:
                            self.logger.warning(f"读取 zip 条目失败: {entry_path}: {e}")
                            self.log_text.append(tr("msg_zip_entry_read_failed", entry=entry_path, error=str(e)))
                            failed += 1

                    self.progress_bar.setValue(idx + 1)
                    if idx % 100 == 0:
                        from PySide6.QtWidgets import QApplication
                        QApplication.processEvents()

        except zipfile.BadZipFile:
            self.log_text.append(tr("msg_error_not_valid_zip"))
            self.download_logger.error(f"无效的压缩包: {zip_path}")
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_not_valid_zip"))
            self.progress_bar.setVisible(False)
            self.log_text.setVisible(False)
            return
        except Exception as e:
            self.log_text.append(tr("msg_parse_zip_error", error=str(e)))
            self.logger.exception(f"解析压缩包失败: {zip_path}")
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_parse_zip_error", error=str(e)))
            self.progress_bar.setVisible(False)
            self.log_text.setVisible(False)
            return

        all_types = list(eq_data_by_type.keys())
        counts = {t: len(eq_data_by_type[t]) for t in all_types}
        baseline_type = max(counts, key=counts.get) if counts else "GraphicEQ"
        self.log_text.append(f"补提取基准: {baseline_type}={counts.get(baseline_type,0)} 条")
        self.download_logger.info(f"补提取基准类型: {baseline_type} ({counts[baseline_type]} 条)")

        eq_name_maps = {
            "GraphicEQ": ["GraphicEQ", "Graphic EQ", "Graphic_EQ", "Graphic-EQ"],
            "ParametricEQ": ["ParametricEQ", "Parametric EQ", "Parametric_EQ", "Parametric-EQ"],
            "FixedBandEQ": ["FixedBandEQ", "Fixed Band EQ", "Fixed_Band_EQ", "Fixed-Band-EQ"],
        }

        patched = 0
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for eq_key, (base_entry, base_source, base_htype, base_model) in path_lookup.get(baseline_type, {}).items():
                for other_type in all_types:
                    if other_type == baseline_type:
                        continue
                    if eq_key in path_lookup.get(other_type, {}):
                        continue

                    dir_part = base_entry.rsplit("/", 1)[0]
                    filename = base_entry.rsplit("/", 1)[-1]

                    found = False
                    for base_kw in eq_name_maps[baseline_type]:
                        if not found:
                            for other_kw in eq_name_maps[other_type]:
                                candidate_filename = filename.replace(base_kw, other_kw)
                                if candidate_filename == filename:
                                    continue
                                candidate_path = f"{dir_part}/{candidate_filename}"
                                if candidate_path in zip_name_set:
                                    try:
                                        content = zf.read(candidate_path).decode('utf-8')
                                    except UnicodeDecodeError:
                                        content = zf.read(candidate_path).decode('latin-1')
                                    except Exception:
                                        continue

                                    eq_data_by_type[other_type][eq_key] = content
                                    self._eq_raw_contents[eq_key] = content
                                    path_lookup.setdefault(other_type, {})[eq_key] = (candidate_path, base_source, base_htype, base_model)
                                    model_fixed = DownloadWorker._fix_escaped_name(base_model)
                                    source_fixed = DownloadWorker._fix_escaped_name(base_source)
                                    htype_fixed = DownloadWorker._fix_escaped_name(base_htype)
                                    items.append({
                                        'display': model_fixed,
                                        'measurer': source_fixed,
                                        'method': htype_fixed,
                                        'brand': source_fixed,
                                        'model': model_fixed,
                                        'measurement': htype_fixed,
                                        'eq_key': eq_key,
                                        'eq_type': other_type
                                    })
                                    success += 1
                                    found = True
                                    patched += 1
                                    self.download_logger.info(f"补提取: [{other_type}] {eq_key} <- {candidate_path}")
                                    break

        if patched > 0:
            self.log_text.append(f"补提取: 已补全 {patched} 条缺失的 EQ 条目")
            self.download_logger.info(f"补提取完成，共补全 {patched} 条缺失的 EQ 条目")

        for eq_type, eq_data in eq_data_by_type.items():
            if eq_data:
                pkl_path = self.eq_pkl_paths[eq_type]
                self.log_text.append(tr("msg_saving_eq_data", name=pkl_path.name))
                try:
                    eq_dir = PathLib(pkl_path).parent
                    eq_dir.mkdir(parents=True, exist_ok=True)
                    with open(pkl_path, 'wb') as f:
                        pickle.dump(eq_data, f, protocol=pickle.HIGHEST_PROTOCOL)
                    self.log_text.append(tr("label_graphic_eq_pkl_saved", count=len(eq_data)))
                    self.download_logger.info(f"{eq_type}.pkl 已保存，包含 {len(eq_data)} 条 EQ 数据")
                except Exception as e:
                    self.log_text.append(tr("msg_save_pkl_failed", error=str(e)))
                    self.logger.exception(f"保存 {eq_type}.pkl 失败")

        self.progress_bar.setVisible(False)

        if items:
            items.sort(key=lambda x: AutoEQDialog._natural_key(x['display']))
            self.all_items = items
            self._populate_table_all()
            self._save_cache(items, self.local_data_dir)

        self.log_text.append(tr("msg_extract_complete", success=success, failed=failed, total=sum(len(d) for d in eq_data_by_type.values())))
        self.download_logger.info(f"提取完成: 成功 {success}, 失败 {failed}")
        self.log_text.setVisible(False)

    def _update_local_repo(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.download_worker.wait(2000)
        default_base = APP_DIR / "AutoEqData"
        default_eq_dir = default_base / "EQ"
        default_eq_dir.mkdir(parents=True, exist_ok=True)

        if not self.local_data_dir or not Path(self.local_data_dir).is_dir():
            self.local_data_dir = str(default_eq_dir)
            self.settings.setValue("auto_eq_local_dir", self.local_data_dir)

        self._start_download()

    def _refresh_cache(self):
        if self.scan_cache_path and self.scan_cache_path.exists():
            self.scan_cache_path.unlink()
        self._load_last_directory_async()

    def _start_download(self):
        self.download_logger.info("开始下载 AutoEQ 数据")
        self._loading = True
        self._download_in_progress = True
        self._batch_timer.stop()
        self._pending_files.clear()
        self.manual_import_btn.setEnabled(False)
        self.update_repo_btn.setEnabled(False)
        self.refresh_cache_btn.setEnabled(False)
        self.ok_button.setEnabled(False)
        self.log_text.clear()
        self.log_text.setVisible(self.show_download_log)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.cancel_download_btn.setVisible(True)

        eq_types = ["GraphicEQ", "ParametricEQ", "FixedBandEQ"]
        self.download_worker = DownloadWorker(str(APP_DIR / "AutoEqData"), eq_types=eq_types)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.log.connect(self._on_download_log)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.file_downloaded.connect(self._add_file_to_table)
        self.download_worker.start()

    def _cancel_download(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.download_worker.wait(2000)
        self._reset_download_ui()

    def _reset_download_ui(self):
        self._process_pending_files()
        self._loading = False
        self._download_in_progress = False
        self.all_items.sort(key=lambda x: self._natural_key(x['display']))
        self._populate_table_all()
        self._save_cache(self.all_items, self.local_data_dir)
        self.manual_import_btn.setEnabled(True)
        self.update_repo_btn.setEnabled(True)
        self.refresh_cache_btn.setEnabled(True)
        self.ok_button.setEnabled(len([it for it in self.all_items if it.get('eq_type') == self._current_eq_type]) > 0)
        self.progress_bar.setVisible(False)
        self.cancel_download_btn.setVisible(False)
        self.log_text.setVisible(False)

    def _on_download_progress(self, current, total):
        if self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_download_log(self, msg):
        self.download_logger.info(msg)
        self.log_text.append(msg)
        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.ensureCursorVisible()

    def _on_download_finished(self, success, failed):
        self._reset_download_ui()
        self.log_text.append(tr("msg_download_complete"))
        self.download_logger.info(f"下载完成，成功: {success}, 失败: {failed}")

    def _add_file_to_table(self, file_info):
        key = (file_info['display'], file_info['measurer'], file_info['method'], file_info.get('eq_type', ''))
        if key in self._existing_keys:
            return
        self._existing_keys.add(key)
        self.all_items.append(file_info)
        if not self._download_in_progress:
            self._save_cache(self.all_items, self.local_data_dir)
        if self._download_in_progress:
            return
        self._pending_files.append(file_info)
        if not self._batch_timer.isActive():
            self._batch_timer.start(self._batch_interval)

    def _process_pending_files(self):
        if not self._pending_files:
            return
        self.table.setUpdatesEnabled(False)
        for file_info in self._pending_files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(file_info['display']))
            self.table.setItem(row, 1, QTableWidgetItem(file_info['measurer']))
            self.table.setItem(row, 2, QTableWidgetItem(file_info['method']))
        self.table.setUpdatesEnabled(True)
        self._pending_files.clear()
        self._displayed_indices = list(range(len(self.all_items)))

    @staticmethod
    def _normalize(text):
        return re.sub(r'[\s\-_\.\(\)\[\]\{\}/\\,\'"]+', '', text).lower()

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        if not b:
            return len(a)
        previous_row = range(len(b) + 1)
        for i, ca in enumerate(a):
            current_row = [i + 1]
            for j, cb in enumerate(b):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (ca != cb)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    @staticmethod
    def _score_item(item, keyword_lower, keyword_norm, keyword_tokens, search_cols):
        score = 0
        for col in search_cols:
            text = item.get(col, '')
            if not text:
                continue
            text_lower = text.lower()
            text_norm = AutoEQDialog._normalize(text)
            col_weight = 1.5 if col == 'display' else 1.0

            if text_lower.startswith(keyword_lower):
                score = max(score, int(100 * col_weight))
            elif text_norm.startswith(keyword_norm):
                score = max(score, int(85 * col_weight))
            elif keyword_lower in text_lower:
                score = max(score, int(60 * col_weight))
            elif keyword_norm in text_norm:
                score = max(score, int(50 * col_weight))
            elif keyword_tokens and all(tok in text_norm for tok in keyword_tokens):
                score = max(score, int(40 * col_weight))

        if score > 0:
            return score

        if len(keyword_norm) >= 2:
            display = item.get('display', '')
            if display:
                display_norm = AutoEQDialog._normalize(display)
                dist = AutoEQDialog._levenshtein(display_norm, keyword_norm)
                if dist <= 2:
                    score = max(score, 10)
                elif dist <= 3:
                    score = max(score, 5)
                elif dist <= 4:
                    score = max(score, 2)
        return score

    def _on_search_input(self):
        self._search_timer.start(150)

    def _on_search_context_menu(self, pos):
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
        copy_action.triggered.connect(self.search_edit.copy)
        menu.addAction(copy_action)
        paste_action = QAction(tr("menu_paste"), self)
        paste_action.triggered.connect(self.search_edit.paste)
        menu.addAction(paste_action)
        cut_action = QAction(tr("menu_cut"), self)
        cut_action.triggered.connect(self.search_edit.cut)
        menu.addAction(cut_action)
        delete_action = QAction(tr("menu_delete"), self)
        delete_action.triggered.connect(self._search_delete)
        menu.addAction(delete_action)
        menu.exec(self.search_edit.mapToGlobal(pos))

    def _search_delete(self):
        self.search_edit.del_()

    def _do_search(self):
        keyword = self.search_edit.text().strip()
        eq_type = self._current_eq_type

        typed_items = []
        for idx, item in enumerate(self.all_items):
            if item.get('eq_type') == eq_type:
                typed_items.append((item, idx))

        if not keyword:
            items = [it for it, _ in typed_items]
            indices = [ai for _, ai in typed_items]
            self._populate_table_from(items, indices)
            QTimer.singleShot(0, self._restore_last_selected)
            return

        keyword_norm = self._normalize(keyword)
        keyword_tokens = [self._normalize(t) for t in keyword.split() if t.strip()]
        keyword_lower = keyword.lower()

        search_cols = []
        if self.search_col_display:
            search_cols.append('display')
        if self.search_col_measurer:
            search_cols.append('measurer')
        if self.search_col_method:
            search_cols.append('method')
        if not search_cols:
            search_cols = ['display', 'measurer', 'method']

        scored = []
        for local_idx, (item, all_idx) in enumerate(typed_items):
            s = self._score_item(item, keyword_lower, keyword_norm, keyword_tokens, search_cols)
            if s > 0:
                scored.append((s, all_idx, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        items = [it for _, _, it in scored]
        indices = [ai for _, ai, _ in scored]
        self._populate_table_from(items, indices)
        self.table.scrollToTop()


    def _on_table_double_clicked(self):
        if self._loading:
            return
        self._download_selected()

    def _download_selected(self):
        if self._loading:
            return
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self._displayed_indices):
            QMessageBox.warning(self, tr("msg_not_selected"), tr("msg_please_select_headphone"))
            return
        item = self.all_items[self._displayed_indices[current_row]]
        eq_key = item.get('eq_key')
        local_path = item.get('local_path')
        eq_type = item.get('eq_type', 'GraphicEQ')

        if eq_key:
            self._set_last_selected(eq_key)
            self._load_eq_content(eq_key, eq_type)
        elif local_path:
            self._set_last_selected(local_path)
            self._load_local_file(local_path, eq_type)
        else:
            QMessageBox.warning(self, tr("dialog_error"), tr("msg_no_valid_data_source"))
            return

    def _load_eq_content(self, eq_key, eq_type="GraphicEQ"):
        self.logger.info(f"从 {eq_type}.pkl 加载: {eq_key}")
        pkl_path = self.eq_pkl_paths.get(eq_type, self.eq_pkl_path)
        try:
            with open(pkl_path, 'rb') as f:
                eq_data = pickle.load(f)
            content = eq_data.get(eq_key)
            if not content:
                QMessageBox.warning(self, tr("dialog_read_error"), tr("msg_not_found_in_pkl", key=eq_key))
                return
        except Exception as e:
            self.logger.exception(f"读取 {eq_type}.pkl 失败: {eq_key}")
            QMessageBox.warning(self, tr("dialog_read_error"), tr("msg_cannot_read_pkl", error=str(e)))
            return

        raw_content = self._eq_raw_contents.get(eq_key, content)
        self._parse_download(content, eq_type, raw_content)

    def _load_local_file(self, file_path, eq_type="GraphicEQ"):
        self.logger.info(f"加载本地文件: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.logger.exception(f"读取文件失败: {file_path}")
            QMessageBox.warning(self, tr("dialog_read_error"), tr("msg_cannot_read_file", error=str(e)))
            return
        raw_content = content
        self._parse_download(content, eq_type, raw_content)

    def _parse_download(self, content, eq_type="GraphicEQ", raw_content=None):
        if raw_content is None:
            raw_content = content

        preamp = 0.0
        gain_map = {}

        if eq_type in ("ParametricEQ", "FixedBandEQ"):
            preamp, gain_map = parse_parametric_to_graphic(content)
        else:
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                lower = line.lower()
                if lower.startswith('preamp:'):
                    parts = line.split()
                    for part in parts:
                        try:
                            preamp = float(part)
                            break
                        except ValueError:
                            continue
                elif 'graphiceq:' in lower:
                    after_colon = line.split(':', 1)[1].strip()
                    pairs = after_colon.split(';')
                    for pair in pairs:
                        pair = pair.strip()
                        if not pair:
                            continue
                        tokens = pair.split()
                        if len(tokens) >= 2:
                            try:
                                freq = float(tokens[0])
                                gain = float(tokens[1])
                                gain_map[freq] = gain
                            except ValueError:
                                pass

        if not gain_map:
            QMessageBox.warning(self, tr("dialog_parse_failed"), tr("msg_no_valid_graphic_eq"))
            self.logger.warning("未找到有效的 EQ 数据")
            return

        gain_map_json = json.dumps(gain_map)
        self.logger.info(f"解析成功，eq_type={eq_type}, preamp={preamp}, 频段数={len(gain_map)}")
        self.dataReady.emit(preamp, gain_map_json, eq_type, raw_content)
        self.accept()

    def _open_auto_eq_url(self):
        url = QUrl("https://github.com/jaakkopasanen/AutoEq")
        QDesktopServices.openUrl(url)

    @staticmethod
    def _create_settings_card(title):
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

        return card, content_layout

    def _open_settings_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dialog_settings_title"))
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet("""
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
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 16, 16, 16)
        scroll_layout.setSpacing(16)

        card_search, layout_search = self._create_settings_card(tr("card_search_scope"))
        search_row = QHBoxLayout()
        search_row.setSpacing(16)

        sw_display = ToggleSwitch(tr("col_headphone"))
        sw_display.setChecked(self.search_col_display)
        sw_display.toggled.connect(lambda checked: self._save_search_col_setting('display', checked))
        search_row.addWidget(sw_display)

        sw_measurer = ToggleSwitch(tr("col_measurer"))
        sw_measurer.setChecked(self.search_col_measurer)
        sw_measurer.toggled.connect(lambda checked: self._save_search_col_setting('measurer', checked))
        search_row.addWidget(sw_measurer)

        sw_method = ToggleSwitch(tr("col_method"))
        sw_method.setChecked(self.search_col_method)
        sw_method.toggled.connect(lambda checked: self._save_search_col_setting('method', checked))
        search_row.addWidget(sw_method)

        layout_search.addLayout(search_row)

        card_log, layout_log = self._create_settings_card(tr("card_repo_management"))
        log_row = QHBoxLayout()
        log_row.setSpacing(16)

        sw_log = ToggleSwitch(tr("toggle_show_log"))
        sw_log.setChecked(self.show_download_log)
        sw_log.toggled.connect(self._save_download_log_setting)
        log_row.addWidget(sw_log)

        sw_folder = ToggleSwitch(tr("toggle_folder_loading"))
        sw_folder.setChecked(self.use_folder_loading)
        sw_folder.toggled.connect(self._save_folder_loading_setting)
        log_row.addWidget(sw_folder)

        layout_log.addLayout(log_row)

        scroll_layout.addWidget(card_search)
        scroll_layout.addWidget(card_log)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        dlg_layout.addWidget(scroll)

        dlg.exec()

    def _save_download_log_setting(self, checked):
        self.show_download_log = checked
        self.settings.setValue("auto_eq_show_download_log", checked)
        self.settings.sync()
        self._set_download_log_level(checked)

    @staticmethod
    def _set_download_log_level(enabled):
        level = logging.DEBUG if enabled else logging.CRITICAL + 1
        for logger_name in ['download', 'urllib3', 'requests', 'requests.packages.urllib3']:
            logging.getLogger(logger_name).setLevel(level)

    def _save_folder_loading_setting(self, checked):
        self.use_folder_loading = checked
        self.settings.setValue("auto_eq_use_folder_loading", checked)
        self.settings.sync()

    def _save_search_col_setting(self, col_name, checked):
        if col_name == 'display':
            self.search_col_display = checked
            self.settings.setValue("auto_eq_search_display", checked)
        elif col_name == 'measurer':
            self.search_col_measurer = checked
            self.settings.setValue("auto_eq_search_measurer", checked)
        elif col_name == 'method':
            self.search_col_method = checked
            self.settings.setValue("auto_eq_search_method", checked)
        self.settings.sync()
        if self.search_edit.text().strip():
            self._do_search()
