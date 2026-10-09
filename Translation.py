import logging
import weakref

_lang = "zh_CN"
_callbacks = []

_translations = {
    "app_title": {
        "zh_CN": "EQAPO 编辑器",
        "zh_TW": "EQAPO 編輯器",
        "en": "EQAPO Editor",
    },
    "tab_speaker": {
        "zh_CN": "扬声器",
        "zh_TW": "揚聲器",
        "en": "Speaker",
    },
    "tab_microphone": {
        "zh_CN": "麦克风",
        "zh_TW": "麥克風",
        "en": "Microphone",
    },
    "tab_config": {
        "zh_CN": "配置",
        "zh_TW": "配寘",
        "en": "Config",
    },
    "tab_settings": {
        "zh_CN": "设置",
        "zh_TW": "設定",
        "en": "Settings",
    },
    "tab_extensions": {
        "zh_CN": "扩展",
        "zh_TW": "擴展",
        "en": "Extensions",
    },
    "config_status_configured": {
        "zh_CN": "已配置",
        "zh_TW": "已配寘",
        "en": "Configured",
    },
    "config_status_not_configured": {
        "zh_CN": "未配置",
        "zh_TW": "未配寘",
        "en": "Not Configured",
    },
    "config_status_speaker_configured": {
        "zh_CN": "扬声器: 已配置",
        "zh_TW": "揚聲器: 已配寘",
        "en": "Speaker: Configured",
    },
    "config_status_mic_configured": {
        "zh_CN": "麦克风: 已配置",
        "zh_TW": "麥克風: 已配寘",
        "en": "Microphone: Configured",
    },
    "card_config_management": {
        "zh_CN": "配置文件管理",
        "zh_TW": "設定檔管理",
        "en": "Config File Management",
    },
    "card_reset_maintenance": {
        "zh_CN": "重置与维护",
        "zh_TW": "重置與維護",
        "en": "Reset & Maintenance",
    },
    "card_app_behavior": {
        "zh_CN": "应用程序行为",
        "zh_TW": "應用程式行為",
        "en": "Application Behavior",
    },
    "card_language": {
        "zh_CN": "语言 / Language",
        "zh_TW": "語言 / Language",
        "en": "Language",
    },
    "btn_select_config_folder": {
        "zh_CN": "选择配置文件夹",
        "zh_TW": "選擇設定資料夾",
        "en": "Select Config Folder",
    },
    "btn_install": {
        "zh_CN": "安装",
        "zh_TW": "安裝",
        "en": "Install",
    },
    "btn_uninstall": {
        "zh_CN": "卸载",
        "zh_TW": "解除安裝",
        "en": "Uninstall",
    },
    "btn_reset_settings": {
        "zh_CN": "重置设置",
        "zh_TW": "重置設定",
        "en": "Reset Settings",
    },
    "btn_clear_logs": {
        "zh_CN": "清除日志",
        "zh_TW": "清除日誌",
        "en": "Clear Logs",
    },
    "btn_open_logs": {
        "zh_CN": "打开日志",
        "zh_TW": "開啟日誌",
        "en": "Open Logs",
    },
    "label_not_selected": {
        "zh_CN": "未选择",
        "zh_TW": "未選擇",
        "en": "Not Selected",
    },
    "label_interface_language": {
        "zh_CN": "界面语言：",
        "zh_TW": "介面語言：",
        "en": "Interface Language:",
    },
    "toggle_tray": {
        "zh_CN": "启用软件托盘（关闭窗口时最小化到托盘）",
        "zh_TW": "啟用軟體系統匣（關閉視窗時最小化到系統匣）",
        "en": "Enable System Tray (minimize to tray on close)",
    },
    "toggle_startup": {
        "zh_CN": "开机自启",
        "zh_TW": "開機自動啟動",
        "en": "Auto Start",
    },
    "tray_show": {
        "zh_CN": "显示窗口",
        "zh_TW": "顯示視窗",
        "en": "Show Window",
    },
    "tray_hide": {
        "zh_CN": "隐藏窗口",
        "zh_TW": "隱藏視窗",
        "en": "Hide Window",
    },
    "tray_exit": {
        "zh_CN": "退出",
        "zh_TW": "退出",
        "en": "Exit",
    },
    "dialog_success": {
        "zh_CN": "成功",
        "zh_TW": "成功",
        "en": "Success",
    },
    "dialog_info": {
        "zh_CN": "信息",
        "zh_TW": "資訊",
        "en": "Info",
    },
    "dialog_error": {
        "zh_CN": "错误",
        "zh_TW": "錯誤",
        "en": "Error",
    },
    "dialog_warning": {
        "zh_CN": "警告",
        "zh_TW": "警告",
        "en": "Warning",
    },
    "dialog_partial_failure": {
        "zh_CN": "部分失败",
        "zh_TW": "部分失敗",
        "en": "Partial Failure",
    },
    "dialog_confirm_uninstall": {
        "zh_CN": "确认卸载",
        "zh_TW": "確認解除安裝",
        "en": "Confirm Uninstall",
    },
    "dialog_confirm": {
        "zh_CN": "确认",
        "zh_TW": "確認",
        "en": "Confirm",
    },
    "msg_logs_cleared": {
        "zh_CN": "已清空日志文件",
        "zh_TW": "已清空日誌檔案",
        "en": "Log files cleared",
    },
    "msg_no_log_dir": {
        "zh_CN": "日志文件夹不存在，没有可清空的日志。",
        "zh_TW": "日誌資料夾不存在，沒有可清空的日誌。",
        "en": "Log directory does not exist, no logs to clear.",
    },
    "msg_no_log_files": {
        "zh_CN": "没有找到日志文件。",
        "zh_TW": "沒有找到日誌檔案。",
        "en": "No log files found.",
    },
    "msg_cannot_clear": {
        "zh_CN": "无法清空以下文件（可能被占用）：\n",
        "zh_TW": "無法清空以下檔案（可能被佔用）：\n",
        "en": "Cannot clear the following files (may be in use):\n",
    },
    "msg_app_exists": {
        "zh_CN": "应用 '{app_name}' 已存在",
        "zh_TW": "應用程式 '{app_name}' 已存在",
        "en": "App '{app_name}' already exists",
    },
    "msg_config_installed": {
        "zh_CN": "配置已安装到 EqualizerAPO",
        "zh_TW": "設定已安裝到 EqualizerAPO",
        "en": "Config installed to EqualizerAPO",
    },
    "msg_uninstalled_restored": {
        "zh_CN": "已卸载自定义配置，并还原为备份。",
        "zh_TW": "已解除安裝自訂設定，並還原為備份。",
        "en": "Custom config uninstalled and backup restored.",
    },
    "msg_uninstalled_no_restore": {
        "zh_CN": "已删除设备文件，但 config.txt 未能还原。\n配置页面已重置为默认设置。",
        "zh_TW": "已刪除裝置檔案，但 config.txt 未能還原。\n設定頁面已重置為預設設定。",
        "en": "Device files removed, but config.txt could not be restored.\nConfig page reset to defaults.",
    },
    "msg_cannot_write_config": {
        "zh_CN": "无法写入 config.txt",
        "zh_TW": "無法寫入 config.txt",
        "en": "Cannot write config.txt",
    },
    "msg_restore_config_error": {
        "zh_CN": "还原 config.txt 时出错: {e}",
        "zh_TW": "還原 config.txt 時發生錯誤: {e}",
        "en": "Error restoring config.txt: {e}",
    },
    "msg_clear_config_error": {
        "zh_CN": "清空 config.txt 失败: {e}",
        "zh_TW": "清空 config.txt 失敗: {e}",
        "en": "Failed to clear config.txt: {e}",
    },
    "msg_no_default_backup": {
        "zh_CN": "未找到默认备份",
        "zh_TW": "未找到預設備份",
        "en": "Default Backup Not Found",
    },
    "msg_no_default_backup_detail": {
        "zh_CN": "未找到默认备份文件 (default_backup/config.txt)\n要继续还原吗？将使用空白默认配置。",
        "zh_TW": "未找到預設備份檔案 (default_backup/config.txt)\n要繼續還原嗎？將使用空白預設設定。",
        "en": "Default backup file not found (default_backup/config.txt)\nContinue restore? A blank default config will be used.",
    },
    "msg_confirm_continue": {
        "zh_CN": "确定要继续吗？",
        "zh_TW": "確定要繼續嗎？",
        "en": "Are you sure you want to continue?",
    },
    "msg_file_not_found": {
        "zh_CN": "文件不存在: {path}",
        "zh_TW": "檔案不存在: {path}",
        "en": "File not found: {path}",
    },
    "msg_cannot_read_file": {
        "zh_CN": "无法读取文件:\n{error}",
        "zh_TW": "無法讀取檔案:\n{error}",
        "en": "Cannot read file:\n{error}",
    },
    "msg_no_config_found": {
        "zh_CN": "未找到配置文件",
        "zh_TW": "未找到設定檔",
        "en": "Config File Not Found",
    },
    "msg_select_valid_config": {
        "zh_CN": "请选择有效的 config.txt 文件",
        "zh_TW": "請選擇有效的 config.txt 檔案",
        "en": "Please select a valid config.txt file",
    },
    "msg_select_apo_dir_first": {
        "zh_CN": "请先选择 EqualizerAPO 目录",
        "zh_TW": "請先選擇 EqualizerAPO 目錄",
        "en": "Please select EqualizerAPO directory first",
    },
    "msg_data_format_error": {
        "zh_CN": "接收到的数据格式错误",
        "zh_TW": "接收到的資料格式錯誤",
        "en": "Received data format error",
    },
    "msg_lang_changed": {
        "zh_CN": '语言已切换为 {lang}。\n点击"是"将自动重启程序以完全生效。',
        "zh_TW": '語言已切換為 {lang}。\n點擊「是」將自動重新啟動程式以完全生效。',
        "en": "Language changed to {lang}.\nClick Yes to restart the program for full effect.",
    },
    "dialog_lang_switch": {
        "zh_CN": "语言",
        "zh_TW": "語言",
        "en": "Language",
    },
    "lang_zh_CN": {
        "zh_CN": "中文（简体）",
        "zh_TW": "中文（簡體）",
        "en": "Chinese (Simplified)",
    },
    "lang_zh_TW": {
        "zh_CN": "中文（繁體）",
        "zh_TW": "中文（繁體）",
        "en": "Chinese (Traditional)",
    },
    "lang_en": {
        "zh_CN": "English",
        "zh_TW": "English",
        "en": "English",
    },
    "tooltip_current_config_path": {
        "zh_CN": "当前配置文件路径",
        "zh_TW": "當前設定檔路徑",
        "en": "Current config file path",
    },
    "placeholder_paste_path": {
        "zh_CN": "可粘贴路径到此...",
        "zh_TW": "可粘貼路徑到此...",
        "en": "Paste path here...",
    },
    "header_apps": {
        "zh_CN": "游戏与应用程序",
        "zh_TW": "遊戲與應用程式",
        "en": "Games & Apps",
    },
    "toggle_auto_switch": {
        "zh_CN": "自动切换配置",
        "zh_TW": "自動切換設定",
        "en": "Auto Switch Config",
    },
    "toggle_resident_config": {
        "zh_CN": "创建默认配置",
        "zh_TW": "建立預設設定",
        "en": "Create Default Config",
    },
    "toggle_exclude_default_config": {
        "zh_CN": "排除默认配置",
        "zh_TW": "排除預設設定",
        "en": "Exclude Default Config",
    },
    "toggle_notification": {
        "zh_CN": "通知",
        "zh_TW": "通知",
        "en": "Notification",
    },
    "toggle_spk_file": {
        "zh_CN": "管理SPK文件",
        "zh_TW": "管理SPK檔案",
        "en": "Manage SPK File",
    },
    "toggle_mic_file": {
        "zh_CN": "管理MIC文件",
        "zh_TW": "管理MIC檔案",
        "en": "Manage MIC File",
    },
    "combo_config_write_mode": {
        "zh_CN": "覆盖配置",
        "zh_TW": "覆蓋設定",
        "en": "Overwrite Config",
    },
    "combo_config_preserve_mode": {
        "zh_CN": "保留配置",
        "zh_TW": "保留設定",
        "en": "Preserve Config",
    },
    "tooltip_save_to_app": {
        "zh_CN": "保存当前配置到此应用",
        "zh_TW": "儲存當前設定到此應用程式",
        "en": "Save current config to this app",
    },
    "tooltip_delete_app": {
        "zh_CN": "删除此应用配置",
        "zh_TW": "刪除此應用程式設定",
        "en": "Delete this app config",
    },
    "hint_app_management": {
        "zh_CN": "点击 {add_icon} 按钮加入游戏或应用程序\n选中卡片修改配置会自动保存到专属配置\n创建默认配置后当专属配置应用程序退出后会回到默认配置",
        "zh_TW": "點擊 {add_icon} 按鈕加入遊戲或應用程式\n選中卡片修改設定會自動儲存到專屬設定\n建立預設設定後當專屬設定應用程式退出後會回到預設設定",
        "en": "Click {add_icon} to add a game or app\nSelect a card and modify config — changes are auto-saved to app-specific config\nAfter creating a default config, it will be restored when the app-specific config app exits",
    },
    "dialog_receiver_data_error": {
        "zh_CN": "接收到的数据格式错误",
        "zh_TW": "接收到的資料格式錯誤",
        "en": "Received data format error",
    },
    "file_filter_exe": {
        "zh_CN": "可执行文件 (*.exe);;所有文件 (*.*)",
        "zh_TW": "可執行檔 (*.exe);;所有檔案 (*.*)",
        "en": "Executable (*.exe);;All Files (*.*)",
    },
    "dialog_select_app": {
        "zh_CN": "选择游戏/应用程序",
        "zh_TW": "選擇遊戲/應用程式",
        "en": "Select Game/App",
    },
    "dialog_select_apo_dir": {
        "zh_CN": "请选择 EqualizerAPO 安装目录",
        "zh_TW": "請選擇 EqualizerAPO 安裝目錄",
        "en": "Select EqualizerAPO Install Directory",
    },
    "dialog_select_config_txt": {
        "zh_CN": "请选择 config.txt 文件",
        "zh_TW": "請選擇 config.txt 檔案",
        "en": "Select config.txt File",
    },
    "dialog_no_config_found": {
        "zh_CN": "未找到配置文件",
        "zh_TW": "未找到設定檔",
        "en": "Config File Not Found",
    },
    "msg_config_not_found_ask_manual": {
        "zh_CN": "在所选文件夹及子文件夹中未找到 config.txt 文件。\n是否手动选择 config.txt 文件？",
        "zh_TW": "在所選資料夾及子資料夾中未找到 config.txt 檔案。\n是否手動選擇 config.txt 檔案？",
        "en": "No config.txt file found in selected folder and subfolders.\nDo you want to manually select a config.txt file?",
    },
    "dialog_install_complete": {
        "zh_CN": "安装完成",
        "zh_TW": "安裝完成",
        "en": "Install Complete",
    },
    "dialog_uninstall_complete": {
        "zh_CN": "卸载完成",
        "zh_TW": "解除安裝完成",
        "en": "Uninstall Complete",
    },
    "msg_uninstall_warning": {
        "zh_CN": "确定要卸载自定义配置吗？\n\n将删除自定义设备文件并还原 config.txt 为备份。",
        "zh_TW": "確定要解除安裝自訂設定嗎？\n\n將刪除自訂裝置檔案並還原 config.txt 為備份。",
        "en": "Are you sure you want to uninstall the custom config?\n\nCustom device files will be deleted and config.txt will be restored to backup.",
    },
    "msg_qt_multimedia_not_installed": {
        "zh_CN": "QtMultimedia模块未安装，音频监听功能不可用",
        "zh_TW": "QtMultimedia模組未安裝，音訊監聽功能不可用",
        "en": "QtMultimedia module not installed, audio monitoring unavailable",
    },
    "msg_config_switched": {
        "zh_CN": "EQAPO 已切换配置",
        "zh_TW": "EQAPO 已切換設定",
        "en": "EQAPO Config Switched",
    },
    "msg_switched_to": {
        "zh_CN": "已切换到: {app_name}",
        "zh_TW": "已切換到: {app_name}",
        "en": "Switched to: {app_name}",
    },
    "msg_switched_back": {
        "zh_CN": "已回退到: EQAPO编辑器",
        "zh_TW": "已退回至: EQAPO編輯器",
        "en": "Reverted to: EQAPO Editor",
    },
    "msg_saved": {
        "zh_CN": "已保存",
        "zh_TW": "已儲存",
        "en": "Saved",
    },
    "msg_closing": {
        "zh_CN": "正在关闭程序，停止所有监听...",
        "zh_TW": "正在關閉程式，停止所有監聽...",
        "en": "Closing program, stopping all monitors...",
    },
    "msg_interrupt": {
        "zh_CN": "收到中断信号，正在退出...",
        "zh_TW": "收到中斷訊號，正在退出...",
        "en": "Interrupt signal received, exiting...",
    },
    "msg_spk_device_no_config": {
        "zh_CN": "扬声器设备已启用但无法生成有效配置，将注释其Include行",
        "zh_TW": "揚聲器裝置已啟用但無法產生有效設定，將註釋其Include行",
        "en": "Speaker device enabled but cannot generate valid config, Include line will be commented",
    },
    "msg_mic_device_no_config": {
        "zh_CN": "麦克风设备已启用但无法生成有效配置，将注释其Include行",
        "zh_TW": "麥克風裝置已啟用但無法產生有效設定，將註釋其Include行",
        "en": "Microphone device enabled but cannot generate valid config, Include line will be commented",
    },
    "label_enable_device": {
        "zh_CN": "启动设备:",
        "zh_TW": "啟動裝置:",
        "en": "Enable Device:",
    },
    "label_device": {
        "zh_CN": "设备:",
        "zh_TW": "裝置:",
        "en": "Device:",
    },
    "label_monitor": {
        "zh_CN": "监听:",
        "zh_TW": "監聽:",
        "en": "Monitor:",
    },
    "label_monitor_off": {
        "zh_CN": "关闭监听",
        "zh_TW": "關閉監聽",
        "en": "Monitor Off",
    },
    "label_monitor_on": {
        "zh_CN": "打开监听",
        "zh_TW": "開啟監聽",
        "en": "Monitor On",
    },
    "label_preamp": {
        "zh_CN": "音量增益:",
        "zh_TW": "音量增益:",
        "en": "Preamp Gain:",
    },
    "label_graphic_eq": {
        "zh_CN": "图形均衡器:",
        "zh_TW": "圖形等化器:",
        "en": "Graphic EQ:",
    },
    "mode_15band": {
        "zh_CN": "15频段",
        "zh_TW": "15頻段",
        "en": "15 Band",
    },
    "mode_31band": {
        "zh_CN": "31频段",
        "zh_TW": "31頻段",
        "en": "31 Band",
    },
    "mode_variable": {
        "zh_CN": "可变频段",
        "zh_TW": "可變頻段",
        "en": "Variable",
    },
    "btn_import_bands": {
        "zh_CN": "导入频段",
        "zh_TW": "匯入頻段",
        "en": "Import Bands",
    },
    "btn_export_bands": {
        "zh_CN": "导出频段",
        "zh_TW": "匯出頻段",
        "en": "Export Bands",
    },
    "btn_refresh_devices": {
        "zh_CN": "刷新设备列表",
        "zh_TW": "重新整理裝置列表",
        "en": "Refresh Device List",
    },
    "dialog_monitor_failed": {
        "zh_CN": "监听失败",
        "zh_TW": "監聽失敗",
        "en": "Monitor Failed",
    },
    "msg_no_mic_selected": {
        "zh_CN": "未启用或未选择麦克风设备",
        "zh_TW": "未啟用或未選擇麥克風裝置",
        "en": "Microphone device not enabled or not selected",
    },
    "msg_no_speaker_selected": {
        "zh_CN": "未启用或未选择扬声器设备",
        "zh_TW": "未啟用或未選擇揚聲器裝置",
        "en": "Speaker device not enabled or not selected",
    },
    "dialog_monitor_error": {
        "zh_CN": "监听错误",
        "zh_TW": "監聽錯誤",
        "en": "Monitor Error",
    },
    "dialog_select_bands_file": {
        "zh_CN": "选择频段文件",
        "zh_TW": "選擇頻段檔案",
        "en": "Select Bands File",
    },
    "dialog_import_failed": {
        "zh_CN": "导入失败",
        "zh_TW": "匯入失敗",
        "en": "Import Failed",
    },
    "msg_no_freq_gain_data": {
        "zh_CN": "文件中未找到有效的频率-增益数据",
        "zh_TW": "檔案中未找到有效的頻率-增益資料",
        "en": "No valid frequency-gain data found in file",
    },
    "dialog_export_bands": {
        "zh_CN": "导出频段文件",
        "zh_TW": "匯出頻段檔案",
        "en": "Export Bands File",
    },
    "dialog_export_success": {
        "zh_CN": "导出成功",
        "zh_TW": "匯出成功",
        "en": "Export Successful",
    },
    "dialog_export_failed": {
        "zh_CN": "导出失败",
        "zh_TW": "匯出失敗",
        "en": "Export Failed",
    },
    "msg_file_saved_to": {
        "zh_CN": "文件已保存到:\n{path}",
        "zh_TW": "檔案已儲存到:\n{path}",
        "en": "File saved to:\n{path}",
    },
    "msg_cannot_write_file": {
        "zh_CN": "无法写入文件:\n{error}",
        "zh_TW": "無法寫入檔案:\n{error}",
        "en": "Cannot write file:\n{error}",
    },
    "label_no_device_found": {
        "zh_CN": "未找到设备",
        "zh_TW": "未找到裝置",
        "en": "No Device Found",
    },
    "label_invalid_file": {
        "zh_CN": "无效文件",
        "zh_TW": "無效檔案",
        "en": "Invalid File",
    },
    "menu_copy": {
        "zh_CN": "复制",
        "zh_TW": "複製",
        "en": "Copy",
    },
    "menu_paste": {
        "zh_CN": "粘贴",
        "zh_TW": "粘貼",
        "en": "Paste",
    },
    "menu_cut": {
        "zh_CN": "剪切",
        "zh_TW": "剪切",
        "en": "Cut",
    },
    "menu_delete": {
        "zh_CN": "删除",
        "zh_TW": "刪除",
        "en": "Delete",
    },
    "msg_config_not_found_in_dir": {
        "zh_CN": "该文件夹中未找到 config.txt 配置文件",
        "zh_TW": "該文件夾中未找到 config.txt 設定檔",
        "en": "config.txt not found in the selected folder",
    },
    "msg_invalid_config_path": {
        "zh_CN": "输入的路径无效，请检查后重试",
        "zh_TW": "輸入的路徑無效，請檢查後重試",
        "en": "Invalid path, please check and try again",
    },
    "label_unavailable": {
        "zh_CN": " (不可用)",
        "zh_TW": " (不可用)",
        "en": " (Unavailable)",
    },
    "dialog_auto_eq_title": {
        "zh_CN": "EQAPO AutoEQ 数据库",
        "zh_TW": "EQAPO AutoEQ 資料庫",
        "en": "EQAPO AutoEQ Database",
    },
    "label_search": {
        "zh_CN": "搜索:",
        "zh_TW": "搜尋:",
        "en": "Search:",
    },
    "placeholder_search": {
        "zh_CN": "输入耳机名称，实时搜索...",
        "zh_TW": "輸入耳機名稱，即時搜尋...",
        "en": "Enter headphone name, real-time search...",
    },
    "btn_settings": {
        "zh_CN": "设置",
        "zh_TW": "設定",
        "en": "Settings",
    },
    "label_eq_type": {
        "zh_CN": "EQ类型",
        "zh_TW": "EQ類型",
        "en": "EQ Type",
    },
    "eq_type_graphic": {
        "zh_CN": "GraphicEQ",
        "zh_TW": "GraphicEQ",
        "en": "GraphicEQ",
    },
    "eq_type_parametric": {
        "zh_CN": "ParametricEQ",
        "zh_TW": "ParametricEQ",
        "en": "ParametricEQ",
    },
    "eq_type_fixed_band": {
        "zh_CN": "FixedBandEQ",
        "zh_TW": "FixedBandEQ",
        "en": "FixedBandEQ",
    },
    "btn_auto_eq_url": {
        "zh_CN": "AutoEQ网址",
        "zh_TW": "AutoEQ網址",
        "en": "AutoEQ URL",
    },
    "col_headphone": {
        "zh_CN": "耳机",
        "zh_TW": "耳機",
        "en": "Headphone",
    },
    "col_measurer": {
        "zh_CN": "测量器",
        "zh_TW": "測量器",
        "en": "Measurer",
    },
    "col_method": {
        "zh_CN": "方法",
        "zh_TW": "方法",
        "en": "Method",
    },
    "btn_browse_local_repo": {
        "zh_CN": "浏览本地仓库",
        "zh_TW": "瀏覽本地倉庫",
        "en": "Browse Local Repo",
    },
    "btn_update_local_repo": {
        "zh_CN": "更新本地仓库",
        "zh_TW": "更新本地倉庫",
        "en": "Update Local Repo",
    },
    "btn_refresh_cache": {
        "zh_CN": "刷新缓存",
        "zh_TW": "重新整理快取",
        "en": "Refresh Cache",
    },
    "btn_cancel_download": {
        "zh_CN": "取消下载",
        "zh_TW": "取消下載",
        "en": "Cancel Download",
    },
    "btn_use": {
        "zh_CN": "使用",
        "zh_TW": "使用",
        "en": "Use",
    },
    "btn_cancel": {
        "zh_CN": "取消",
        "zh_TW": "取消",
        "en": "Cancel",
    },
    "dialog_settings_title": {
        "zh_CN": "AutoEQ 设置",
        "zh_TW": "AutoEQ 設定",
        "en": "AutoEQ Settings",
    },
    "card_search_scope": {
        "zh_CN": "搜索范围",
        "zh_TW": "搜尋範圍",
        "en": "Search Scope",
    },
    "card_repo_management": {
        "zh_CN": "仓库管理",
        "zh_TW": "倉庫管理",
        "en": "Repo Management",
    },
    "toggle_show_log": {
        "zh_CN": "显示日志框",
        "zh_TW": "顯示日誌框",
        "en": "Show Log Panel",
    },
    "toggle_folder_loading": {
        "zh_CN": "从文件夹加载EQ数据",
        "zh_TW": "從資料夾載入EQ資料",
        "en": "Load EQ Data from Folder",
    },
    "msg_scanning": {
        "zh_CN": "正在扫描本地数据请稍候...",
        "zh_TW": "正在掃描本地資料請稍候...",
        "en": "Scanning local data, please wait...",
    },
    "msg_downloading": {
        "zh_CN": "正在下载 AutoEQ 仓库 zip 包...",
        "zh_TW": "正在下載 AutoEQ 倉庫 zip 套件...",
        "en": "Downloading AutoEQ repo zip...",
    },
    "msg_user_abort": {
        "zh_CN": "用户中止下载",
        "zh_TW": "使用者中止下載",
        "en": "Download aborted by user",
    },
    "msg_connecting_github": {
        "zh_CN": "正在连接 GitHub... (尝试 {retry}/{max})",
        "zh_TW": "正在連線 GitHub... (嘗試 {retry}/{max})",
        "en": "Connecting to GitHub... (attempt {retry}/{max})",
    },
    "msg_download_failed": {
        "zh_CN": "下载失败: {error}",
        "zh_TW": "下載失敗: {error}",
        "en": "Download failed: {error}",
    },
    "msg_network_retry": {
        "zh_CN": "网络波动，自动重试 {retry}/{max}",
        "zh_TW": "網路波動，自動重試 {retry}/{max}",
        "en": "Network fluctuation, auto retry {retry}/{max}",
    },
    "msg_downloading_data": {
        "zh_CN": "正在下载数据...",
        "zh_TW": "正在下載資料...",
        "en": "Downloading data...",
    },
    "msg_download_aborted": {
        "zh_CN": "下载被用户中止",
        "zh_TW": "下載被使用者中止",
        "en": "Download aborted by user",
    },
    "msg_parsing_zip": {
        "zh_CN": "正在解析 ZIP 并提取 EQ 数据...",
        "zh_TW": "正在解析 ZIP 並提取 EQ 資料...",
        "en": "Parsing ZIP and extracting EQ data...",
    },
    "msg_parse_zip_failed": {
        "zh_CN": "解析 ZIP 文件失败: {error}",
        "zh_TW": "解析 ZIP 檔案失敗: {error}",
        "en": "Failed to parse ZIP: {error}",
    },
    "msg_parse_complete": {
        "zh_CN": "解析完成，共 {total} 个文件，正在提取 EQ 内容...",
        "zh_TW": "解析完成，共 {total} 個檔案，正在提取 EQ 內容...",
        "en": "Parsing complete, {total} files, extracting EQ content...",
    },
    "msg_no_downloadable_files": {
        "zh_CN": "未找到任何可下载的文件",
        "zh_TW": "未找到任何可下載的檔案",
        "en": "No downloadable files found",
    },
    "msg_saving_eq_data": {
        "zh_CN": "正在保存 EQ 数据到 {name}...",
        "zh_TW": "正在儲存 EQ 資料到 {name}...",
        "en": "Saving EQ data to {name}...",
    },
    "msg_save_pkl_failed": {
        "zh_CN": "保存 GraphicEQ.pkl 失败: {error}",
        "zh_TW": "儲存 GraphicEQ.pkl 失敗: {error}",
        "en": "Failed to save GraphicEQ.pkl: {error}",
    },
    "msg_update_complete": {
        "zh_CN": "更新完成: 成功 {success}, 失败 {failed}, 共 {total} 条 EQ 数据已保存到 GraphicEQ.pkl",
        "zh_TW": "更新完成: 成功 {success}, 失敗 {failed}, 共 {total} 條 EQ 資料已儲存到 GraphicEQ.pkl",
        "en": "Update complete: {success} succeeded, {failed} failed, {total} EQ entries saved to GraphicEQ.pkl",
    },
    "dialog_select_repo_root": {
        "zh_CN": "选择仓库根目录",
        "zh_TW": "選擇倉庫根目錄",
        "en": "Select Repository Root",
    },
    "dialog_select_zip": {
        "zh_CN": "选择 AutoEQ 压缩包",
        "zh_TW": "選擇 AutoEQ 壓縮包",
        "en": "Select AutoEQ Archive",
    },
    "msg_parsing_zip_file": {
        "zh_CN": "正在解析压缩包: {name}",
        "zh_TW": "正在解析壓縮包: {name}",
        "en": "Parsing archive: {name}",
    },
    "msg_found_graphic_eq": {
        "zh_CN": "找到 {total} 个 GraphicEQ.txt 文件",
        "zh_TW": "找到 {total} 個 GraphicEQ.txt 檔案",
        "en": "Found {total} GraphicEQ.txt files",
    },
    "msg_not_valid_zip": {
        "zh_CN": "选择的文件不是有效的压缩包",
        "zh_TW": "選擇的檔案不是有效的壓縮包",
        "en": "Selected file is not a valid archive",
    },
    "msg_error_not_valid_zip": {
        "zh_CN": "错误：选择的文件不是有效的压缩包",
        "zh_TW": "錯誤：選擇的檔案不是有效的壓縮包",
        "en": "Error: Selected file is not a valid archive",
    },
    "msg_parse_zip_error": {
        "zh_CN": "解析压缩包失败:\n{error}",
        "zh_TW": "解析壓縮包失敗:\n{error}",
        "en": "Failed to parse archive:\n{error}",
    },
    "msg_no_valid_eq_data": {
        "zh_CN": "未找到任何有效的 EQ 数据",
        "zh_TW": "未找到任何有效的 EQ 資料",
        "en": "No valid EQ data found",
    },
    "msg_extract_complete": {
        "zh_CN": "提取完成: 成功 {success}, 失败 {failed}, 共 {total} 条 EQ 数据",
        "zh_TW": "提取完成: 成功 {success}, 失敗 {failed}, 共 {total} 條 EQ 資料",
        "en": "Extraction complete: {success} succeeded, {failed} failed, {total} EQ entries",
    },
    "msg_download_complete": {
        "zh_CN": "下载完成",
        "zh_TW": "下載完成",
        "en": "Download Complete",
    },
    "msg_not_selected": {
        "zh_CN": "未选择",
        "zh_TW": "未選擇",
        "en": "Not Selected",
    },
    "msg_please_select_headphone": {
        "zh_CN": "请先选择耳机",
        "zh_TW": "請先選擇耳機",
        "en": "Please select a headphone first",
    },
    "msg_no_valid_data_source": {
        "zh_CN": "所选条目无有效数据源",
        "zh_TW": "所選條目無有效資料來源",
        "en": "Selected entry has no valid data source",
    },
    "dialog_read_error": {
        "zh_CN": "读取错误",
        "zh_TW": "讀取錯誤",
        "en": "Read Error",
    },
    "msg_not_found_in_pkl": {
        "zh_CN": "GraphicEQ.pkl 中未找到: {key}",
        "zh_TW": "GraphicEQ.pkl 中未找到: {key}",
        "en": "Not found in GraphicEQ.pkl: {key}",
    },
    "msg_cannot_read_pkl": {
        "zh_CN": "无法读取 GraphicEQ.pkl:\n{error}",
        "zh_TW": "無法讀取 GraphicEQ.pkl:\n{error}",
        "en": "Cannot read GraphicEQ.pkl:\n{error}",
    },
    "dialog_parse_failed": {
        "zh_CN": "解析失败",
        "zh_TW": "解析失敗",
        "en": "Parse Failed",
    },
    "msg_no_valid_graphic_eq": {
        "zh_CN": "未找到有效的 GraphicEQ 数据",
        "zh_TW": "未找到有效的 GraphicEQ 資料",
        "en": "No valid GraphicEQ data found",
    },
    "msg_audio_monitor_log": {
        "zh_CN": "监听运行错误，请查看日志文件",
        "zh_TW": "監聽執行錯誤，請查看日誌檔案",
        "en": "Monitor runtime error, please check log file",
    },
    "file_filter_text": {
        "zh_CN": "文本文件 (*.txt *.csv);;所有文件 (*.*)",
        "zh_TW": "文字檔案 (*.txt *.csv);;所有檔案 (*.*)",
        "en": "Text Files (*.txt *.csv);;All Files (*.*)",
    },
    "file_filter_txt": {
        "zh_CN": "文本文件 (*.txt);;所有文件 (*.*)",
        "zh_TW": "文字檔案 (*.txt);;所有檔案 (*.*)",
        "en": "Text Files (*.txt);;All Files (*.*)",
    },
    "file_filter_config_txt": {
        "zh_CN": "配置文件 (config.txt);;所有文件 (*.*)",
        "zh_TW": "設定檔 (config.txt);;所有檔案 (*.*)",
        "en": "Config File (config.txt);;All Files (*.*)",
    },
    "file_filter_zip": {
        "zh_CN": "压缩文件 (*.zip);;所有文件 (*.*)",
        "zh_TW": "壓縮檔案 (*.zip);;所有檔案 (*.*)",
        "en": "Archive Files (*.zip);;All Files (*.*)",
    },
    "label_graphic_eq_pkl_saved": {
        "zh_CN": "GraphicEQ.pkl 已保存，包含 {count} 条 EQ 数据",
        "zh_TW": "GraphicEQ.pkl 已儲存，包含 {count} 條 EQ 資料",
        "en": "GraphicEQ.pkl saved, containing {count} EQ entries",
    },
    "btn_channel_balance": {
        "zh_CN": "声道平衡",
        "zh_TW": "聲道平衡",
        "en": "Channel Balance",
    },
    "dialog_channel_balance_title": {
        "zh_CN": "声道平衡",
        "zh_TW": "聲道平衡",
        "en": "Channel Balance",
    },
    "label_balance": {
        "zh_CN": "平衡调节",
        "zh_TW": "平衡調節",
        "en": "Balance Adjustment",
    },
    "label_left_channel": {
        "zh_CN": "左声道",
        "zh_TW": "左聲道",
        "en": "Left",
    },
    "label_right_channel": {
        "zh_CN": "右声道",
        "zh_TW": "右聲道",
        "en": "Right",
    },
    "btn_reset": {
        "zh_CN": "重置",
        "zh_TW": "重置",
        "en": "Reset",
    },
    "btn_ok": {
        "zh_CN": "确定",
        "zh_TW": "確定",
        "en": "OK",
    },
    "msg_zip_entry_read_failed": {
        "zh_CN": "读取ZIP条目失败: {entry} - {error}",
        "zh_TW": "讀取ZIP條目失敗: {entry} - {error}",
        "en": "Failed to read ZIP entry: {entry} - {error}",
    },
    "msg_decode_fallback": {
        "zh_CN": "UTF-8解码失败，已降级为latin-1: {entry}",
        "zh_TW": "UTF-8解碼失敗，已降級為latin-1: {entry}",
        "en": "UTF-8 decode failed, fallback to latin-1: {entry}",
    },
    "msg_dir_scan_failed": {
        "zh_CN": "目录扫描失败: {error}",
        "zh_TW": "目錄掃描失敗: {error}",
        "en": "Directory scan failed: {error}",
    },
    "msg_dir_entry_failed": {
        "zh_CN": "处理文件失败: {file} - {error}",
        "zh_TW": "處理文件失敗: {file} - {error}",
        "en": "Failed to process file: {file} - {error}",
    },
    "msg_pkl_corrupted_fallback": {
        "zh_CN": "缓存文件损坏，尝试降级读取: {path}",
        "zh_TW": "緩存文件損壞，嘗試降級讀取: {path}",
        "en": "Cache file corrupted, attempting fallback read: {path}",
    },
    "msg_eq_type_not_found": {
        "zh_CN": "未找到 {eq_type} 类型的EQ数据",
        "zh_TW": "未找到 {eq_type} 類型的EQ數據",
        "en": "No {eq_type} EQ data found",
    },
    "msg_no_valid_graphic_eq": {
        "zh_CN": "未找到有效的EQ均衡器数据",
        "zh_TW": "未找到有效的EQ均衡器數據",
        "en": "No valid EQ data found",
    },
    "placeholder_ext_path": {
        "zh_CN": "输入或粘贴应用程序路径，回车确认",
        "zh_TW": "輸入或粘貼應用程式路徑，按 Enter 確認",
        "en": "Enter or paste an app path, press Enter to confirm",
    },
    "btn_browse": {
        "zh_CN": "浏览",
        "zh_TW": "瀏覽",
        "en": "Browse",
    },
    "file_filter_executable": {
        "zh_CN": "可执行文件 (*.exe *.bat *.cmd *.lnk *.com);;所有文件 (*.*)",
        "zh_TW": "可執行檔 (*.exe *.bat *.cmd *.lnk *.com);;所有檔案 (*.*)",
        "en": "Executable (*.exe *.bat *.cmd *.lnk *.com);;All Files (*.*)",
    },
    "file_filter_app": {
        "zh_CN": "应用程序 (*.app);;所有文件 (*.*)",
        "zh_TW": "應用程式 (*.app);;所有檔案 (*.*)",
        "en": "Application (*.app);;All Files (*.*)",
    },
    "dialog_select_extension": {
        "zh_CN": "选择扩展应用程序",
        "zh_TW": "選擇擴展應用程式",
        "en": "Select Extension App",
    },
    "dialog_add_failed": {
        "zh_CN": "添加失败",
        "zh_TW": "新增失敗",
        "en": "Add Failed",
    },
    "msg_cannot_add_extension": {
        "zh_CN": "无法添加扩展应用:\n{error}",
        "zh_TW": "無法新增擴展應用程式:\n{error}",
        "en": "Cannot add extension app:\n{error}",
    },
    "msg_extension_exists": {
        "zh_CN": "该扩展应用已存在。",
        "zh_TW": "該擴展應用程式已存在。",
        "en": "This extension app already exists.",
    },
    "msg_extension_exists_config": {
        "zh_CN": "该扩展应用已在配置中存在。",
        "zh_TW": "該擴展應用程式已在設定中存在。",
        "en": "This extension app already exists in the configuration.",
    },
    "msg_add_extension_error": {
        "zh_CN": "添加扩展应用时发生错误:\n{error}",
        "zh_TW": "新增擴展應用程式時發生錯誤:\n{error}",
        "en": "Error adding extension app:\n{error}",
    },
    "dialog_confirm_remove": {
        "zh_CN": "确认移除",
        "zh_TW": "確認移除",
        "en": "Confirm Remove",
    },
    "msg_confirm_remove_extension": {
        "zh_CN": "确定要移除扩展应用 \"{app_name}\" 吗？",
        "zh_TW": "確定要移除擴展應用程式 \"{app_name}\" 嗎？",
        "en": "Remove extension app \"{app_name}\"?",
    },
    "dialog_remove_failed": {
        "zh_CN": "移除失败",
        "zh_TW": "移除失敗",
        "en": "Remove Failed",
    },
    "msg_remove_extension_error": {
        "zh_CN": "移除扩展应用时发生错误:\n{error}",
        "zh_TW": "移除擴展應用程式時發生錯誤:\n{error}",
        "en": "Error removing extension app:\n{error}",
    },
    "dialog_launch_failed": {
        "zh_CN": "启动失败",
        "zh_TW": "啟動失敗",
        "en": "Launch Failed",
    },
    "msg_cannot_launch_extension": {
        "zh_CN": "无法启动扩展应用:\n{error}",
        "zh_TW": "無法啟動擴展應用程式:\n{error}",
        "en": "Cannot launch extension app:\n{error}",
    },
    "msg_launch_extension_error": {
        "zh_CN": "启动扩展应用时发生错误:\n{error}",
        "zh_TW": "啟動擴展應用程式時發生錯誤:\n{error}",
        "en": "Error launching extension app:\n{error}",
    },
    "msg_path_empty": {
        "zh_CN": "路径为空",
        "zh_TW": "路徑為空",
        "en": "Path is empty",
    },
    "msg_path_not_exist": {
        "zh_CN": "路径不存在: {path}",
        "zh_TW": "路徑不存在: {path}",
        "en": "Path does not exist: {path}",
    },
    "msg_path_not_file": {
        "zh_CN": "路径不是有效的文件: {path}",
        "zh_TW": "路徑不是有效的檔案: {path}",
        "en": "Path is not a valid file: {path}",
    },
    "msg_unsupported_file_type": {
        "zh_CN": "不支持的文件类型: {ext}",
        "zh_TW": "不支援的檔案類型: {ext}",
        "en": "Unsupported file type: {ext}",
    },
    "msg_file_size_zero": {
        "zh_CN": "文件大小为 0 字节",
        "zh_TW": "檔案大小為 0 位元組",
        "en": "File size is 0 bytes",
    },
    "msg_file_too_large": {
        "zh_CN": "文件过大 ({size} MB)，疑似非应用程序",
        "zh_TW": "檔案過大 ({size} MB)，疑似非應用程式",
        "en": "File too large ({size} MB), likely not an application",
    },
    "msg_cannot_read_file_info": {
        "zh_CN": "无法读取文件信息",
        "zh_TW": "無法讀取檔案資訊",
        "en": "Cannot read file info",
    },
    "err_shell_exec_file_not_found": {
        "zh_CN": "文件未找到",
        "zh_TW": "檔案未找到",
        "en": "File not found",
    },
    "err_shell_exec_path_not_found": {
        "zh_CN": "路径未找到",
        "zh_TW": "路徑未找到",
        "en": "Path not found",
    },
    "err_shell_exec_access_denied": {
        "zh_CN": "访问被拒绝",
        "zh_TW": "存取被拒絕",
        "en": "Access denied",
    },
    "err_shell_exec_out_of_memory": {
        "zh_CN": "内存不足",
        "zh_TW": "記憶體不足",
        "en": "Out of memory",
    },
    "err_shell_exec_bad_format": {
        "zh_CN": "错误的执行格式",
        "zh_TW": "錯誤的執行格式",
        "en": "Bad executable format",
    },
    "err_shell_exec_invalid_exe": {
        "zh_CN": "无效的可执行文件",
        "zh_TW": "無效的可執行檔",
        "en": "Invalid executable",
    },
    "err_shell_exec_sharing_violation": {
        "zh_CN": "共享违规",
        "zh_TW": "共用違規",
        "en": "Sharing violation",
    },
    "err_shell_exec_incomplete_assoc": {
        "zh_CN": "文件名关联不完整或无效",
        "zh_TW": "檔案名稱關聯不完整或無效",
        "en": "Incomplete or invalid file association",
    },
    "err_shell_exec_dde_timeout": {
        "zh_CN": "DDE 事务超时",
        "zh_TW": "DDE 事務逾時",
        "en": "DDE transaction timed out",
    },
    "err_shell_exec_dde_fail": {
        "zh_CN": "DDE 事务失败",
        "zh_TW": "DDE 事務失敗",
        "en": "DDE transaction failed",
    },
    "err_shell_exec_dde_busy": {
        "zh_CN": "DDE 事务繁忙",
        "zh_TW": "DDE 事務忙碌",
        "en": "DDE transaction busy",
    },
    "err_shell_exec_no_assoc": {
        "zh_CN": "无关联应用程序",
        "zh_TW": "無關聯應用程式",
        "en": "No associated application",
    },
    "err_shell_exec_dll_not_found": {
        "zh_CN": "DLL 未找到",
        "zh_TW": "DLL 未找到",
        "en": "DLL not found",
    },
    "err_shell_exec_unknown": {
        "zh_CN": "未知错误 (代码: {code})",
        "zh_TW": "未知錯誤 (代碼: {code})",
        "en": "Unknown error (code: {code})",
    },
    "err_shell_exec_failed": {
        "zh_CN": "ShellExecute 失败: {error}",
        "zh_TW": "ShellExecute 失敗: {error}",
        "en": "ShellExecute failed: {error}",
    },
    "btn_open_extension": {
        "zh_CN": "打开扩展",
        "zh_TW": "開啟擴展",
        "en": "Open Extension",
    },
    "toggle_silent_startup": {
        "zh_CN": "启动",
        "zh_TW": "啟動",
        "en": "Startup",
    },
}


_qt_translations = {
    "OK":     {"zh_CN": "确定",     "zh_TW": "確定",     "en": "OK"},
    "&OK":    {"zh_CN": "确定(&O)", "zh_TW": "確定(&O)", "en": "&OK"},
    "Cancel": {"zh_CN": "取消",     "zh_TW": "取消",     "en": "Cancel"},
    "&Cancel":{"zh_CN": "取消(&C)", "zh_TW": "取消(&C)", "en": "&Cancel"},
    "Yes":    {"zh_CN": "是",       "zh_TW": "是",       "en": "Yes"},
    "&Yes":   {"zh_CN": "是(&Y)",   "zh_TW": "是(&Y)",   "en": "&Yes"},
    "No":     {"zh_CN": "否",       "zh_TW": "否",       "en": "No"},
    "&No":    {"zh_CN": "否(&N)",   "zh_TW": "否(&N)",   "en": "&No"},
    "Save":   {"zh_CN": "保存",     "zh_TW": "儲存",     "en": "Save"},
    "&Save":  {"zh_CN": "保存(&S)", "zh_TW": "儲存(&S)", "en": "&Save"},
    "Open":   {"zh_CN": "打开",     "zh_TW": "開啟",     "en": "Open"},
    "&Open":  {"zh_CN": "打开(&O)", "zh_TW": "開啟(&O)", "en": "&Open"},
    "Close":  {"zh_CN": "关闭",     "zh_TW": "關閉",     "en": "Close"},
    "&Close": {"zh_CN": "关闭(&C)", "zh_TW": "關閉(&C)", "en": "&Close"},
    "Apply":  {"zh_CN": "应用",     "zh_TW": "套用",     "en": "Apply"},
    "&Apply": {"zh_CN": "应用(&A)", "zh_TW": "套用(&A)", "en": "&Apply"},
    "Reset":  {"zh_CN": "重置",     "zh_TW": "重設",     "en": "Reset"},
    "&Reset": {"zh_CN": "重置(&R)", "zh_TW": "重設(&R)", "en": "&Reset"},
    "Help":   {"zh_CN": "帮助",     "zh_TW": "說明",     "en": "Help"},
    "&Help":  {"zh_CN": "帮助(&H)", "zh_TW": "說明(&H)", "en": "&Help"},
    "Retry":  {"zh_CN": "重试",     "zh_TW": "重試",     "en": "Retry"},
    "&Retry": {"zh_CN": "重试(&R)", "zh_TW": "重試(&R)", "en": "&Retry"},
    "Ignore": {"zh_CN": "忽略",     "zh_TW": "忽略",     "en": "Ignore"},
    "&Ignore":{"zh_CN": "忽略(&I)", "zh_TW": "忽略(&I)", "en": "&Ignore"},
    "Abort":  {"zh_CN": "中止",     "zh_TW": "中止",     "en": "Abort"},
    "&Abort": {"zh_CN": "中止(&A)", "zh_TW": "中止(&A)", "en": "&Abort"},
    "Discard":{"zh_CN": "放弃",     "zh_TW": "放棄",     "en": "Discard"},
    "&Discard":{"zh_CN": "放弃(&D)","zh_TW": "放棄(&D)", "en": "&Discard"},

    "Open File":        {"zh_CN": "打开文件",     "zh_TW": "開啟檔案",     "en": "Open File"},
    "Save File":        {"zh_CN": "保存文件",     "zh_TW": "儲存檔案",     "en": "Save File"},
    "Choose Directory": {"zh_CN": "选择目录",     "zh_TW": "選擇目錄",     "en": "Choose Directory"},
    "Open Files":       {"zh_CN": "打开文件",     "zh_TW": "開啟檔案",     "en": "Open Files"},
    "Save As":          {"zh_CN": "另存为",       "zh_TW": "另存新檔",     "en": "Save As"},
}

from PySide6.QtCore import QTranslator

class _QtTranslator(QTranslator):

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        text = _qt_translations.get(sourceText, {}).get(_lang)
        if text is not None:
            return text
        return ""


def install_qt_translator(app):
    translator = _QtTranslator(app)
    app.installTranslator(translator)
    logging.getLogger("Translation").info("Qt 系统翻译器已安装")



def tr(key, **kwargs):
    text = _translations.get(key, {}).get(_lang, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def set_language(lang):
    global _lang, _callbacks
    _lang = lang
    logging.getLogger("Translation").info(f"语言切换为: {lang}")
    try:
        import shiboken6
    except ImportError:
        shiboken6 = None
    dead_refs = []
    for ref in _callbacks:
        cb = ref()
        if cb is None:
            dead_refs.append(ref)
            continue
        if shiboken6 is not None:
            instance = getattr(cb, "__self__", None)
            if instance is not None:
                try:
                    if not shiboken6.isValid(instance):
                        dead_refs.append(ref)
                        continue
                except TypeError:
                    pass
        try:
            cb()
        except Exception as e:
            logging.getLogger("Translation").error(f"语言切换回调失败: {e}")
    for ref in dead_refs:
        try:
            _callbacks.remove(ref)
        except ValueError:
            pass


def on_language_changed(callback):
    try:
        ref = weakref.WeakMethod(callback)
    except TypeError:
        ref = weakref.ref(callback)
    _callbacks.append(ref)


def get_language():
    return _lang