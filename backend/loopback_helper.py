"""
Loopback Helper - Manages v4l2loopback virtual camera devices.
Allows writing digitally zoomed/processed frames into a virtual webcam device
for consumption by Zoom, MS Teams, Google Meet, OBS, and browsers.
"""

import os
import fcntl
import struct
import subprocess
import glob
from typing import Optional, Dict, Any, Tuple

# V4L2 Constants
VIDIOC_S_FMT = 0xc0cc5605
V4L2_BUF_TYPE_VIDEO_OUTPUT = 2
V4L2_PIX_FMT_YUYV = 0x56595559  # 'YUYV'
V4L2_PIX_FMT_BGR24 = 0x33524742 # 'BGR3'
V4L2_PIX_FMT_RGB24 = 0x33424752 # 'RGB3'
V4L2_FIELD_NONE = 1

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
            
            # struct v4l2_format {
            #     __u32 type;
            #     union {
            #         struct v4l2_pix_format pix;
            #         ...
            #     } fmt;
            # };
            # struct v4l2_pix_format {
            #     __u32 width;
            #     __u32 height;
            #     __u32 pixelformat;
            #     __u32 field;
            #     __u32 bytesperline;
            #     __u32 sizeimage;
            #     __u32 colorspace;
            #     __u32 priv;
            #     __u32 flags;
            #     __u32 ycbcr_enc;
            #     __u32 quantization;
            #     __u32 xfer_func;
            # };
            
            fourcc = V4L2_PIX_FMT_YUYV
            bytes_per_line = self.width * 2
            size_image = self.width * self.height * 2
            colorspace = 8 # V4L2_COLORSPACE_SRGB

            # Format structure: 204 bytes total (type + pix_format + padding)
            fmt_struct = struct.pack(
                "IIIIIIIIIIIII",
                V4L2_BUF_TYPE_VIDEO_OUTPUT, # type
                self.width,                 # width
                self.height,                # height
                fourcc,                     # pixelformat
                V4L2_FIELD_NONE,            # field
                bytes_per_line,             # bytesperline
                size_image,                 # sizeimage
                colorspace,                 # colorspace
                0,                          # priv
                0,                          # flags
                0,                          # ycbcr_enc
                0,                          # quantization
                0                           # xfer_func
            )
            fmt_struct = fmt_struct.ljust(208, b'\x00')

            fcntl.ioctl(self.fd, VIDIOC_S_FMT, fmt_struct)
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
        except Exception as e:
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
