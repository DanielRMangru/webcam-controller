"""
Loopback Helper - Manages v4l2loopback virtual camera devices.
Allows writing digitally zoomed/processed frames into a virtual webcam device
for consumption by Zoom, MS Teams, Google Meet, OBS, and browsers.
"""

import os
import fcntl
import ctypes
import glob
from typing import Optional, Dict, Any

# V4L2 Constants
# On 64-bit Linux (x86_64), sizeof(v4l2_format) is 208 bytes, giving 0xc0d05605
VIDIOC_S_FMT = 0xc0d05605
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_PIX_FMT_YUYV = 0x56595559  # 'YUYV'
V4L2_FIELD_NONE = 1
V4L2_COLORSPACE_SRGB = 8

class v4l2_pix_format(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("pixelformat", ctypes.c_uint32),
        ("field", ctypes.c_uint32),
        ("bytesperline", ctypes.c_uint32),
        ("sizeimage", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("priv", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("ycbcr_enc", ctypes.c_uint32),
        ("quantization", ctypes.c_uint32),
        ("xfer_func", ctypes.c_uint32),
    ]

class v4l2_format(ctypes.Structure):
    class _fmt(ctypes.Union):
        _fields_ = [
            ("pix", v4l2_pix_format),
            ("raw_data", ctypes.c_uint8 * 200),
            ("_align", ctypes.c_uint64),
        ]
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32), # 4 bytes padding for 64-bit union alignment (total 208 bytes)
        ("fmt", _fmt),
    ]

class LoopbackDeviceWriter:
    def __init__(self, device_path: str = "/dev/video10", width: int = 1280, height: int = 720, fps: int = 30):
        self.device_path = device_path
        self.width = width
        self.height = height
        self.fps = fps
        self.fd: Optional[int] = None
        self.is_open = False
        self.pixel_format = "YUYV"

    def open(self) -> bool:
        """Open loopback device and configure video output format."""
        if not os.path.exists(self.device_path):
            print(f"[Loopback] Device {self.device_path} does not exist.")
            return False

        try:
            self.fd = os.open(self.device_path, os.O_RDWR)
            
            fmt = v4l2_format()
            fmt.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
            fmt.fmt.pix.width = self.width
            fmt.fmt.pix.height = self.height
            fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV
            fmt.fmt.pix.field = V4L2_FIELD_NONE
            fmt.fmt.pix.bytesperline = self.width * 2
            fmt.fmt.pix.sizeimage = self.width * self.height * 2
            fmt.fmt.pix.colorspace = V4L2_COLORSPACE_SRGB

            fcntl.ioctl(self.fd, VIDIOC_S_FMT, fmt)
            self.is_open = True
            print(f"[Loopback] Successfully initialized {self.device_path} ({self.width}x{self.height} @ {self.fps}fps)")
            return True
        except Exception as e:
            print(f"[Loopback] Error initializing {self.device_path}: {e}")
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except Exception:
                    pass
                self.fd = None
            self.is_open = False
            return False

    def write_frame_yuyv(self, yuyv_bytes: bytes) -> bool:
        """Write raw YUYV bytes to the virtual camera device."""
        if not self.is_open or self.fd is None:
            return False
        try:
            os.write(self.fd, yuyv_bytes)
            return True
        except Exception:
            return False

    def close(self):
        """Close the loopback device."""
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None
        self.is_open = False


class LoopbackManager:
    @staticmethod
    def is_module_loaded() -> bool:
        """Check if v4l2loopback kernel module is loaded in /proc/modules."""
        try:
            with open("/proc/modules", "r") as f:
                return "v4l2loopback" in f.read()
        except Exception:
            return False

    @staticmethod
    def get_loopback_devices() -> list:
        """Find existing loopback device paths."""
        loopbacks = []
        for dev in glob.glob("/dev/video*"):
            # Check sysfs driver name
            dev_num = dev.replace("/dev/video", "")
            sys_path = f"/sys/class/video4linux/video{dev_num}/name"
            if os.path.exists(sys_path):
                try:
                    with open(sys_path, "r") as f:
                        name = f.read().strip()
                        if "loopback" in name.lower() or "virtual" in name.lower() or "controller" in name.lower():
                            loopbacks.append({"device": dev, "name": name})
                except Exception:
                    pass
        return loopbacks

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """Get overall loopback virtual camera status."""
        loaded = LoopbackManager.is_module_loaded()
        devices = LoopbackManager.get_loopback_devices()
        has_video10 = os.path.exists("/dev/video10")

        return {
            "module_loaded": loaded,
            "devices": devices,
            "recommended_device": "/dev/video10" if has_video10 or not devices else (devices[0]["device"] if devices else "/dev/video10"),
            "ready": loaded and (len(devices) > 0 or has_video10),
            "setup_command": "sudo modprobe v4l2loopback devices=1 video_nr=10 card_label='Webcam Controller Virtual Cam' exclusive_caps=1"
        }
