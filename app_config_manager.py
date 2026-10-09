import sys
import json
import logging
from pathlib import Path

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()

from PySide6.QtCore import QSettings

def get_settings_path():
    config_dir = APP_DIR / "EQapoConfig"
    config_dir.mkdir(exist_ok=True)
    return str(config_dir / "settings.ini")

DEFAULT_CONFIG = {
    "output": {
        "device_name": None,
        "preamp": 0.0,
        "mode": "15频段",
        "variable_freqs": None,
        "gain_map": {},
        "channel_balance": {"left": 0.0, "right": 0.0}
    },
    "input": {
        "device_name": None,
        "preamp": 0.0,
        "mode": "15频段",
        "variable_freqs": None,
        "gain_map": {},
        "channel_balance": {"left": 0.0, "right": 0.0}
    }
}


RESIDENT_KEY = "__resident__"


class AppConfigManager:
    APP_CONFIG_PREFIX = "app_config/"
    APP_LIST_KEY = "app_list"

    def __init__(self):
        self.settings = QSettings(get_settings_path(), QSettings.IniFormat)
        self.logger = logging.getLogger(f"{__name__}.AppConfigManager")

    def _make_key(self, app_path):
        if app_path == RESIDENT_KEY:
            return f"{self.APP_CONFIG_PREFIX}{RESIDENT_KEY}"
        normalized = Path(app_path).resolve()
        return f"{self.APP_CONFIG_PREFIX}{str(normalized)}"

    def _normalize_path(self, app_path):
        if app_path == RESIDENT_KEY:
            return RESIDENT_KEY
        return str(Path(app_path).resolve())

    def _get_app_list(self):
        raw = self.settings.value(self.APP_LIST_KEY, None)
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

    def _set_app_list(self, app_list):
        self.settings.setValue(self.APP_LIST_KEY, json.dumps(app_list, ensure_ascii=False))
        self.settings.sync()

    def get_app_config(self, app_path):
        key = self._make_key(app_path)
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

    def save_app_config(self, app_path, app_name, config_data):
        key = self._make_key(app_path)
        full_config = {
            "app_name": app_name,
            "app_path": self._normalize_path(app_path),
            "output": config_data.get("output", DEFAULT_CONFIG["output"].copy()),
            "input": config_data.get("input", DEFAULT_CONFIG["input"].copy()),
            "detection": config_data.get("detection", {})
        }
        self.settings.setValue(key, json.dumps(full_config, ensure_ascii=False))
        app_list = self._get_app_list()
        normalized = self._normalize_path(app_path)
        if normalized not in app_list:
            app_list.append(normalized)
            self._set_app_list(app_list)
        self.settings.sync()
        self.logger.info(f"保存应用配置: {app_name} ({normalized})")

    def delete_app_config(self, app_path):
        key = self._make_key(app_path)
        self.settings.remove(key)
        app_list = self._get_app_list()
        normalized = self._normalize_path(app_path)
        if normalized in app_list:
            app_list.remove(normalized)
            self._set_app_list(app_list)
        self.settings.sync()
        self.logger.info(f"删除应用配置: {normalized}")

    def get_all_apps(self):
        app_list = self._get_app_list()
        apps = []
        for app_path in app_list:
            config = self.get_app_config(app_path)
            if config is not None:
                apps.append({
                    "app_name": config.get("app_name", Path(app_path).stem),
                    "app_path": app_path,
                    "config": config
                })
            else:
                apps.append({
                    "app_name": Path(app_path).stem,
                    "app_path": app_path,
                    "config": None
                })
        return apps

    def get_app_by_path(self, app_path):
        config = self.get_app_config(app_path)
        if config is None:
            return None
        return {
            "app_name": config.get("app_name", Path(app_path).stem),
            "app_path": self._normalize_path(app_path),
            "config": config
        }

    def get_output_config(self, app_path):
        config = self.get_app_config(app_path)
        if config is None:
            return None
        return config.get("output", DEFAULT_CONFIG["output"].copy())

    def get_input_config(self, app_path):
        config = self.get_app_config(app_path)
        if config is None:
            return None
        return config.get("input", DEFAULT_CONFIG["input"].copy())

    def save_output_config(self, app_path, app_name, output_config):
        existing = self.get_app_config(app_path)
        if existing is None:
            full_config = DEFAULT_CONFIG.copy()
            full_config["app_name"] = app_name
            full_config["app_path"] = self._normalize_path(app_path)
        else:
            full_config = existing
        full_config["output"] = output_config
        self.save_app_config(app_path, app_name, full_config)

    def save_input_config(self, app_path, app_name, input_config):
        existing = self.get_app_config(app_path)
        if existing is None:
            full_config = DEFAULT_CONFIG.copy()
            full_config["app_name"] = app_name
            full_config["app_path"] = self._normalize_path(app_path)
        else:
            full_config = existing
        full_config["input"] = input_config
        self.save_app_config(app_path, app_name, full_config)

    def clear_all_app_configs(self):
        for app_path in list(self._get_app_list()):
            key = self._make_key(app_path)
            self.settings.remove(key)
        self.settings.remove(self.APP_LIST_KEY)
        self.settings.sync()

    def get_app_list_str(self):
        return json.dumps(self._get_app_list(), ensure_ascii=False)

    def has_config(self, app_path):
        return self.get_app_config(app_path) is not None

    def get_detection_config(self, app_path):
        config = self.get_app_config(app_path)
        if config is None:
            return None
        return config.get("detection", {})

    def save_detection_config(self, app_path, app_name, detection_config):
        existing = self.get_app_config(app_path)
        if existing is None:
            full_config = {
                "app_name": app_name,
                "app_path": self._normalize_path(app_path),
                "output": DEFAULT_CONFIG["output"].copy(),
                "input": DEFAULT_CONFIG["input"].copy(),
                "detection": detection_config
            }
        else:
            full_config = existing
            full_config["detection"] = detection_config
        self.save_app_config(app_path, app_name, full_config)

    def get_app_aliases(self, app_path):
        detection = self.get_detection_config(app_path)
        if detection is None:
            return []
        return detection.get("aliases", [])

    def set_app_aliases(self, app_path, app_name, aliases):
        detection = self.get_detection_config(app_path) or {}
        detection["aliases"] = list(aliases)
        self.save_detection_config(app_path, app_name, detection)

    def add_app_alias(self, app_path, app_name, alias):
        detection = self.get_detection_config(app_path) or {}
        aliases = detection.get("aliases", [])
        if alias not in aliases:
            aliases.append(alias)
        detection["aliases"] = aliases
        self.save_detection_config(app_path, app_name, detection)

    def remove_app_alias(self, app_path, app_name, alias):
        detection = self.get_detection_config(app_path) or {}
        aliases = detection.get("aliases", [])
        if alias in aliases:
            aliases.remove(alias)
        detection["aliases"] = aliases
        self.save_detection_config(app_path, app_name, detection)

    def get_all_app_detection_rules(self):
        apps = self.get_all_apps()
        rules = {}
        for app in apps:
            detection = app.get("config", {}).get("detection", {})
            if detection:
                rules[app["app_path"]] = detection
        return rules


app_config_manager = AppConfigManager()