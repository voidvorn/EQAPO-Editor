import sys
from pathlib import Path
from PySide6.QtCore import QSettings

def get_app_dir():
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).parent
    else:
        return Path(sys.argv[0]).resolve().parent

APP_DIR = get_app_dir()

def get_settings_path():
    config_dir = APP_DIR / "EQapoConfig"
    config_dir.mkdir(exist_ok=True)
    return str(config_dir / "settings.ini")

class ConfigKeys:
    TRAY_ENABLED = "tray_enabled"
    LAST_CONFIG_PATH = "last_config_path"
    LAST_APO_PATH = "last_apo_path"
    AUTO_SWITCH_ENABLED = "auto_switch_enabled"
    NOTIFICATION_ENABLED = "notification_enabled"
    RESIDENT_CONFIG_ENABLED = "resident_config_enabled"
    EXCLUDE_DEFAULT_CONFIG = "exclude_default_config"
    LAST_ACTIVE_APP = "last_active_app"
    LANGUAGE = "language"
    SPK_ENABLED = "spk_enabled"
    MIC_ENABLED = "mic_enabled"
    CONFIG_WRITE_MODE = "config_write_mode"
    
    def MONITOR_STATE(device_type):
        return f"monitor_state_{device_type}"
    
    OUTPUT_DEVICE_NAME = "output_device_name"
    OUTPUT_PREAMP = "output_preamp"
    OUTPUT_MODE = "output_mode"
    OUTPUT_VARIABLE_FREQS = "output_variable_freqs"
    OUTPUT_GAIN_MAP = "output_gain_map"
    
    INPUT_DEVICE_NAME = "input_device_name"
    INPUT_PREAMP = "input_preamp"
    INPUT_MODE = "input_mode"
    INPUT_VARIABLE_FREQS = "input_variable_freqs"
    INPUT_GAIN_MAP = "input_gain_map"
    
    OUTPUT_LEFT_BALANCE = "output_left_balance"
    OUTPUT_RIGHT_BALANCE = "output_right_balance"
    INPUT_LEFT_BALANCE = "input_left_balance"
    INPUT_RIGHT_BALANCE = "input_right_balance"

class ConfigManager:
    def __init__(self):
        self.settings = QSettings(get_settings_path(), QSettings.IniFormat)
    
    def get_tray_enabled(self):
        return self.settings.value(ConfigKeys.TRAY_ENABLED, False, bool)
    
    def set_tray_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.TRAY_ENABLED, enabled)
    
    def get_last_config_path(self):
        return self.settings.value(ConfigKeys.LAST_CONFIG_PATH, "")
    
    def set_last_config_path(self, path):
        self.settings.setValue(ConfigKeys.LAST_CONFIG_PATH, path)
    
    def get_last_apo_path(self):
        return self.settings.value(ConfigKeys.LAST_APO_PATH, "")
    
    def set_last_apo_path(self, path):
        self.settings.setValue(ConfigKeys.LAST_APO_PATH, path)
    
    def get_monitor_state(self, device_type):
        return self.settings.value(ConfigKeys.MONITOR_STATE(device_type), 0, int)
    
    def set_monitor_state(self, device_type, state):
        self.settings.setValue(ConfigKeys.MONITOR_STATE(device_type), state)
    
    def get_output_device_name(self):
        return self.settings.value(ConfigKeys.OUTPUT_DEVICE_NAME, None)
    
    def set_output_device_name(self, name):
        self.settings.setValue(ConfigKeys.OUTPUT_DEVICE_NAME, name)
    
    def get_output_preamp(self):
        return self.settings.value(ConfigKeys.OUTPUT_PREAMP, 0.0, float)
    
    def set_output_preamp(self, value):
        self.settings.setValue(ConfigKeys.OUTPUT_PREAMP, value)
    
    def get_output_mode(self):
        return self.settings.value(ConfigKeys.OUTPUT_MODE, "15频段")
    
    def set_output_mode(self, mode):
        self.settings.setValue(ConfigKeys.OUTPUT_MODE, mode)
    
    def get_output_variable_freqs(self):
        from Graphic_EQualizer import EQTab
        default = EQTab.DEFAULT_VARIABLE_FREQS.copy()
        return self.settings.value(ConfigKeys.OUTPUT_VARIABLE_FREQS, default)
    
    def set_output_variable_freqs(self, freqs):
        self.settings.setValue(ConfigKeys.OUTPUT_VARIABLE_FREQS, freqs)
    
    def get_output_gain_map(self):
        return self.settings.value(ConfigKeys.OUTPUT_GAIN_MAP, {})
    
    def set_output_gain_map(self, gain_map):
        self.settings.setValue(ConfigKeys.OUTPUT_GAIN_MAP, gain_map)
    
    def get_input_device_name(self):
        return self.settings.value(ConfigKeys.INPUT_DEVICE_NAME, None)
    
    def set_input_device_name(self, name):
        self.settings.setValue(ConfigKeys.INPUT_DEVICE_NAME, name)
    
    def get_input_preamp(self):
        return self.settings.value(ConfigKeys.INPUT_PREAMP, 0.0, float)
    
    def set_input_preamp(self, value):
        self.settings.setValue(ConfigKeys.INPUT_PREAMP, value)
    
    def get_input_mode(self):
        return self.settings.value(ConfigKeys.INPUT_MODE, "15频段")
    
    def set_input_mode(self, mode):
        self.settings.setValue(ConfigKeys.INPUT_MODE, mode)
    
    def get_input_variable_freqs(self):
        from Graphic_EQualizer import EQTab
        default = EQTab.DEFAULT_VARIABLE_FREQS.copy()
        return self.settings.value(ConfigKeys.INPUT_VARIABLE_FREQS, default)
    
    def set_input_variable_freqs(self, freqs):
        self.settings.setValue(ConfigKeys.INPUT_VARIABLE_FREQS, freqs)
    
    def get_input_gain_map(self):
        return self.settings.value(ConfigKeys.INPUT_GAIN_MAP, {})
    
    def set_input_gain_map(self, gain_map):
        self.settings.setValue(ConfigKeys.INPUT_GAIN_MAP, gain_map)
    
    def get_output_channel_balance(self):
        left = self.settings.value(ConfigKeys.OUTPUT_LEFT_BALANCE, 0.0, float)
        right = self.settings.value(ConfigKeys.OUTPUT_RIGHT_BALANCE, 0.0, float)
        return left, right
    
    def set_output_channel_balance(self, left, right):
        self.settings.setValue(ConfigKeys.OUTPUT_LEFT_BALANCE, left)
        self.settings.setValue(ConfigKeys.OUTPUT_RIGHT_BALANCE, right)
    
    def get_input_channel_balance(self):
        left = self.settings.value(ConfigKeys.INPUT_LEFT_BALANCE, 0.0, float)
        right = self.settings.value(ConfigKeys.INPUT_RIGHT_BALANCE, 0.0, float)
        return left, right
    
    def set_input_channel_balance(self, left, right):
        self.settings.setValue(ConfigKeys.INPUT_LEFT_BALANCE, left)
        self.settings.setValue(ConfigKeys.INPUT_RIGHT_BALANCE, right)
    
    def get_auto_switch_enabled(self):
        return self.settings.value(ConfigKeys.AUTO_SWITCH_ENABLED, False, bool)
    
    def set_auto_switch_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.AUTO_SWITCH_ENABLED, enabled)
    
    def get_notification_enabled(self):
        return self.settings.value(ConfigKeys.NOTIFICATION_ENABLED, True, bool)
    
    def set_notification_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.NOTIFICATION_ENABLED, enabled)
    
    def get_resident_config_enabled(self):
        return self.settings.value(ConfigKeys.RESIDENT_CONFIG_ENABLED, True, bool)
    
    def set_resident_config_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.RESIDENT_CONFIG_ENABLED, enabled)
    
    def get_exclude_default_config(self):
        return self.settings.value(ConfigKeys.EXCLUDE_DEFAULT_CONFIG, True, bool)
    
    def set_exclude_default_config(self, enabled):
        self.settings.setValue(ConfigKeys.EXCLUDE_DEFAULT_CONFIG, enabled)
    
    def get_last_active_app(self):
        return self.settings.value(ConfigKeys.LAST_ACTIVE_APP, "")
    
    def set_last_active_app(self, app_path):
        self.settings.setValue(ConfigKeys.LAST_ACTIVE_APP, app_path)
    
    def get_language(self):
        return self.settings.value(ConfigKeys.LANGUAGE, "zh_CN")
    
    def set_language(self, lang):
        self.settings.setValue(ConfigKeys.LANGUAGE, lang)
    
    def get_spk_enabled(self):
        return self.settings.value(ConfigKeys.SPK_ENABLED, True, bool)
    
    def set_spk_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.SPK_ENABLED, enabled)
    
    def get_mic_enabled(self):
        return self.settings.value(ConfigKeys.MIC_ENABLED, True, bool)
    
    def set_mic_enabled(self, enabled):
        self.settings.setValue(ConfigKeys.MIC_ENABLED, enabled)
    
    def get_config_write_mode(self):
        return self.settings.value(ConfigKeys.CONFIG_WRITE_MODE, "overwrite")
    
    def set_config_write_mode(self, mode):
        self.settings.setValue(ConfigKeys.CONFIG_WRITE_MODE, mode)
    
    def clear_all(self):
        self.settings.clear()
        self.settings.sync()
    
    def sync(self):
        self.settings.sync()

config_manager = ConfigManager()