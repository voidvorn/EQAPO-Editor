import logging
import threading
from functools import lru_cache
from PySide6.QtCore import QByteArray, QTimer
import numpy

class AudioMonitor:

    def __init__(self, input_device, output_device, error_callback):
        self.logger = logging.getLogger(f"{__name__}.AudioMonitor")
        self.input_device = input_device
        self.output_device = output_device
        self.error_callback = error_callback
        self._running = False
        self._thread = None
        self._stream = None
        self._lock = threading.Lock()
        self.input_index = None
        self.output_index = None
        self.sample_rate = 48000
        self.channels = 2

    @classmethod
    @lru_cache(maxsize=32)
    def _qaudio_to_sd_index_cached(cls, desc, qid_str, direction):
        import sounddevice as sd
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            if qid_str and (qid_str in dev['name'] or dev['name'] in qid_str):
                if direction == 'input' and dev['max_input_channels'] > 0:
                    return idx
                if direction == 'output' and dev['max_output_channels'] > 0:
                    return idx
            if desc.lower() in dev['name'].lower():
                if direction == 'input' and dev['max_input_channels'] > 0:
                    return idx
                if direction == 'output' and dev['max_output_channels'] > 0:
                    return idx
        return None

    def _qaudio_to_sd_index(self, qaudio_dev, direction):
        if not qaudio_dev:
            return None
        desc = qaudio_dev.description()
        qid = qaudio_dev.id()
        if isinstance(qid, QByteArray):
            qid_str = bytes(qid).decode('utf-8', errors='ignore')
        elif isinstance(qid, bytes):
            qid_str = qid.decode('utf-8', errors='ignore')
        else:
            qid_str = str(qid)
        self.logger.debug(f"尝试匹配设备: desc={desc}, qid={qid_str}, direction={direction}")
        return self._qaudio_to_sd_index_cached(desc, qid_str, direction)

    def start(self):
        self.logger.info("尝试启动音频监听")
        try:
            fmt = self.input_device.preferredFormat()
            self.sample_rate = fmt.sampleRate()
            self.channels = fmt.channelCount()
            self.logger.debug(f"音频格式: sample_rate={self.sample_rate}, channels={self.channels}")
        except Exception as e:
            self.logger.exception("获取音频格式失败")
            self.error_callback(f"获取音频格式失败: {str(e)}")
            return

        self.input_index = self._qaudio_to_sd_index(self.input_device, 'input')
        self.output_index = self._qaudio_to_sd_index(self.output_device, 'output')

        if self.input_index is None:
            self.error_callback("未找到对应的麦克风设备")
            self.logger.error("未找到对应的麦克风设备")
            return
        if self.output_index is None:
            self.error_callback("未找到对应的扬声器设备")
            self.logger.error("未找到对应的扬声器设备")
            return

        with self._lock:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self.logger.info("音频监听启动成功")

    def stop(self):
        self.logger.info("停止音频监听")
        with self._lock:
            self._running = False
            if hasattr(self, '_stop_event'):
                self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self):
        import sounddevice as sd
        def callback(inidata, outdata, frames, time_info, status):
            if status:
                logging.warning(f"音频回调状态: {status}")
            outdata[:] = inidata

        try:
            with self._lock:
                if not self._running:
                    return
                self._stream = sd.Stream(
                    device=(self.input_index, self.output_index),
                    samplerate=self.sample_rate,
                    blocksize=512,
                    channels=self.channels,
                    dtype='float32',
                    latency='high',
                    callback=callback
                )
                self._stream.start()
                self.logger.debug("音频流已启动")

            self._stop_event = threading.Event()
            self._stop_event.wait()
        except Exception:
            self.logger.exception("音频监听线程异常")
            QTimer.singleShot(0, lambda: self.error_callback("监听运行错误，请查看日志文件"))
        finally:
            with self._lock:
                if self._stream:
                    try:
                        self._stream.stop()
                        self._stream.close()
                        self.logger.debug("音频流已关闭")
                    except Exception as e:
                        self.logger.exception("关闭音频流异常")
                    self._stream = None
                self._running = False
