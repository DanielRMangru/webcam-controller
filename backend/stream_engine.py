"""
Stream Engine - Video processing, Digital Zoom, Pan/Tilt, Face-Tracking Auto-Zoom,
and Loopback Virtual Camera Pipeline.
"""

import os
import cv2
import time
import threading
import numpy as np
from typing import Optional, Dict, Any, Tuple
from .loopback_helper import LoopbackDeviceWriter, LoopbackManager
from .segmentation_engine import SegmentationEngine

class StreamEngine:
    def __init__(self, device_path: str = "/dev/video0", target_width: int = 1280, target_height: int = 720, target_fps: int = 30):
        self.device_path = device_path
        self.target_width = target_width
        self.target_height = target_height
        self.target_fps = target_fps

        # Zoom and framing parameters
        self.zoom_level = 1.0        # 1.0x to 5.0x
        self.pan_x = 0.0             # -1.0 (left) to +1.0 (right)
        self.pan_y = 0.0             # -1.0 (top) to +1.0 (bottom)
        
        # Auto-Zoom / Face Tracking state
        self.auto_zoom_enabled = False
        self.face_smoothing_alpha = 0.12 # Smoothing factor (0.05 to 0.3)
        self.target_face_ratio = 0.28   # Face height / frame height desired ratio
        self.show_face_box = False      # Whether to draw bounding box on preview
        self.flip_horizontal = False    # Horizontal mirror

        # Smoothed actual coordinates (for interpolation)
        self._curr_zoom = 1.0
        self._curr_pan_x = 0.0
        self._curr_pan_y = 0.0

        # Video capture & thread control
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Output frames
        self.latest_frame_bgr: Optional[np.ndarray] = None
        self.latest_preview_jpeg: Optional[bytes] = None
        self.last_frame_time = time.time()
        self.current_fps = 0.0
        self.detected_faces_count = 0
        self.last_face_rect: Optional[Tuple[int, int, int, int]] = None

        # Virtual camera loopback
        self.virtual_cam_enabled = False
        self.virtual_device_path = "/dev/video10"
        self.loopback_writer: Optional[LoopbackDeviceWriter] = None

        # Segmentation & Virtual Background Engine
        self.seg_engine = SegmentationEngine(target_width=self.target_width, target_height=self.target_height)

        # Initialize Face Detector
        self._init_face_detector()

    def _init_face_detector(self):
        """Initialize OpenCV Face Classifier."""
        self.face_cascade = None
        model_paths = [
            os.path.join(os.path.dirname(__file__), "models", "haarcascade_frontalface_default.xml"),
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        ]
        for p in model_paths:
            if os.path.exists(p):
                try:
                    cascade = cv2.CascadeClassifier(p)
                    if not cascade.empty():
                        self.face_cascade = cascade
                        print(f"[StreamEngine] Face detector loaded from {p}")
                        break
                except Exception as e:
                    print(f"[StreamEngine] Failed to load cascade from {p}: {e}")

    def start(self) -> bool:
        """Start video capture and processing thread."""
        if self.is_running:
            return True

        self.is_running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[StreamEngine] Processing thread started for {self.device_path}.")
        return True

    def stop(self):
        """Stop video capture thread and release resources."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        print("[StreamEngine] Stopped.")

    def set_camera_device(self, new_device_path: str) -> bool:
        """Switch physical camera input device."""
        if new_device_path == self.device_path and self.is_running:
            return True
        self.stop()
        self.device_path = new_device_path
        return self.start()

    def set_zoom(self, zoom: float, pan_x: Optional[float] = None, pan_y: Optional[float] = None):
        """Set manual zoom level (1.0 to 5.0) and optional pan/tilt."""
        with self._lock:
            self.zoom_level = max(1.0, min(5.0, float(zoom)))
            if pan_x is not None:
                self.pan_x = max(-1.0, min(1.0, float(pan_x)))
            if pan_y is not None:
                self.pan_y = max(-1.0, min(1.0, float(pan_y)))

    def set_pan_tilt(self, pan_x: float, pan_y: float):
        """Set pan and tilt offsets (-1.0 to 1.0)."""
        with self._lock:
            self.pan_x = max(-1.0, min(1.0, float(pan_x)))
            self.pan_y = max(-1.0, min(1.0, float(pan_y)))

    def set_auto_zoom(self, enabled: bool, smoothing: Optional[float] = None):
        """Enable or disable Auto-Zoom (Face Tracking)."""
        with self._lock:
            self.auto_zoom_enabled = bool(enabled)
            if smoothing is not None:
                self.face_smoothing_alpha = max(0.01, min(0.5, float(smoothing)))

    def set_virtual_cam(self, enabled: bool, device_path: Optional[str] = None) -> Dict[str, Any]:
        """Enable or disable streaming to v4l2loopback virtual camera."""
        with self._lock:
            self.virtual_cam_enabled = bool(enabled)
            if device_path:
                self.virtual_device_path = device_path

            if self.virtual_cam_enabled:
                if not self.loopback_writer or self.loopback_writer.device_path != self.virtual_device_path:
                    self.loopback_writer = LoopbackDeviceWriter(
                        device_path=self.virtual_device_path,
                        width=self.target_width,
                        height=self.target_height,
                        fps=self.target_fps
                    )
                success = self.loopback_writer.open()
                if not success:
                    self.virtual_cam_enabled = False
                    return {
                        "success": False,
                        "error": f"Failed to open loopback device {self.virtual_device_path}. Make sure v4l2loopback module is loaded.",
                        "setup_hint": "Run: sudo modprobe v4l2loopback devices=1 video_nr=10 card_label='Webcam Controller Virtual Cam' exclusive_caps=1"
                    }
                return {"success": True, "device": self.virtual_device_path, "active": True}
            else:
                if self.loopback_writer:
                    self.loopback_writer.close()
                    self.loopback_writer = None
                return {"success": True, "active": False}

    def _process_auto_framing(self, frame_bgr: np.ndarray, orig_w: int, orig_h: int):
        """Detect face and compute target framing & zoom."""
        if not self.auto_zoom_enabled or self.face_cascade is None:
            self.detected_faces_count = 0
            self.last_face_rect = None
            return

        # Downscale for fast face detection
        detect_w = 400
        scale = detect_w / orig_w
        detect_h = int(orig_h * scale)
        small_frame = cv2.resize(frame_bgr, (detect_w, detect_h))
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(int(35 * scale * (orig_h / 480)), int(35 * scale * (orig_h / 480)))
        )

        self.detected_faces_count = len(faces)
        if len(faces) > 0:
            # Pick the largest face (closest to camera)
            largest_face = max(faces, key=lambda r: r[2] * r[3])
            fx, fy, fw, fh = largest_face
            
            # Convert back to original frame coordinates
            orig_fx = int(fx / scale)
            orig_fy = int(fy / scale)
            orig_fw = int(fw / scale)
            orig_fh = int(fh / scale)
            self.last_face_rect = (orig_fx, orig_fy, orig_fw, orig_fh)

            # Desired face center
            face_center_x = orig_fx + orig_fw / 2.0
            face_center_y = orig_fy + orig_fh / 2.0

            # Compute target zoom: desired face height should be ~target_face_ratio of frame
            current_face_ratio = orig_fh / orig_h
            if current_face_ratio > 0.05:
                calc_target_zoom = self.target_face_ratio / current_face_ratio
                target_zoom = max(1.0, min(3.5, calc_target_zoom))
            else:
                target_zoom = 1.0

            # Target pan/tilt to center the face with headroom
            # Normalize to -1.0 to 1.0
            target_pan_x = (face_center_x - (orig_w / 2.0)) / (orig_w / 2.0)
            # Aim slightly above face center (chin-to-forehead framing headroom)
            target_pan_y = (face_center_y - (orig_h * 0.45)) / (orig_h / 2.0)

            # Clamp targets
            target_pan_x = max(-1.0, min(1.0, target_pan_x))
            target_pan_y = max(-1.0, min(1.0, target_pan_y))

            # Update target zoom and pan with deadband filtering to prevent jitter
            with self._lock:
                if abs(target_zoom - self.zoom_level) > 0.08:
                    self.zoom_level = target_zoom
                if abs(target_pan_x - self.pan_x) > 0.05:
                    self.pan_x = target_pan_x
                if abs(target_pan_y - self.pan_y) > 0.05:
                    self.pan_y = target_pan_y

    def _apply_digital_crop_and_zoom(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Apply smooth digital zoom, pan, tilt, and interpolation."""
        h, w = frame_bgr.shape[:2]

        # Smooth transition towards target zoom and pan/tilt
        alpha = self.face_smoothing_alpha if self.auto_zoom_enabled else 0.25
        self._curr_zoom += alpha * (self.zoom_level - self._curr_zoom)
        self._curr_pan_x += alpha * (self.pan_x - self._curr_pan_x)
        self._curr_pan_y += alpha * (self.pan_y - self._curr_pan_y)

        # If practically 1.0x with no pan, return original resized to target
        if abs(self._curr_zoom - 1.0) < 0.005 and abs(self._curr_pan_x) < 0.005 and abs(self._curr_pan_y) < 0.005:
            if (w, h) != (self.target_width, self.target_height):
                return cv2.resize(frame_bgr, (self.target_width, self.target_height), interpolation=cv2.INTER_LINEAR)
            return frame_bgr

        # Calculate crop dimensions
        crop_w = int(w / self._curr_zoom)
        crop_h = int(h / self._curr_zoom)

        # Maximum available pan range
        max_pan_x = (w - crop_w) / 2.0
        max_pan_y = (h - crop_h) / 2.0

        # Calculate top-left corner
        center_x = (w / 2.0) + (self._curr_pan_x * max_pan_x)
        center_y = (h / 2.0) + (self._curr_pan_y * max_pan_y)

        x1 = int(center_x - crop_w / 2.0)
        y1 = int(center_y - crop_h / 2.0)
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        # Bounds safety clamping
        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > w:
            x1 -= (x2 - w)
            x2 = w
        if y2 > h:
            y1 -= (y2 - h)
            y2 = h

        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(x1 + 1, min(w, x2))
        y2 = max(y1 + 1, min(h, y2))

        cropped = frame_bgr[y1:y2, x1:x2]
        
        # Upscale cropped region with cubic interpolation for sharp detail
        zoomed = cv2.resize(cropped, (self.target_width, self.target_height), interpolation=cv2.INTER_CUBIC)
        return zoomed

    def _capture_loop(self):
        """Worker loop that continuously captures frames and performs processing."""
        try:
            dev_idx = int(self.device_path.replace("/dev/video", "")) if "/dev/video" in self.device_path else 0
        except ValueError:
            dev_idx = 0

        self.cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.device_path)

        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

        fps_count = 0
        fps_timer = time.time()

        try:
            while self.is_running:
                if self.cap is None or not self.cap.isOpened():
                    time.sleep(0.1)
                    continue

                ret, raw_frame = self.cap.read()
                if not ret or raw_frame is None:
                    time.sleep(0.03)
                    continue

                orig_h, orig_w = raw_frame.shape[:2]

                # Auto-framing detection step
                if self.auto_zoom_enabled:
                    self._process_auto_framing(raw_frame, orig_w, orig_h)

                # Apply digital zoom and framing
                processed_frame = self._apply_digital_crop_and_zoom(raw_frame)

                # Optional horizontal mirror
                if self.flip_horizontal:
                    processed_frame = cv2.flip(processed_frame, 1)

                # Apply Virtual Background / Blur / Green Screen if enabled
                if self.seg_engine.enabled:
                    processed_frame = self.seg_engine.process_frame(processed_frame)

                # Write to virtual camera loopback device if active
                if self.virtual_cam_enabled and self.loopback_writer and self.loopback_writer.is_open:
                    try:
                        # Convert BGR to YUYV
                        yuyv_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2YUV_YUYV)
                        self.loopback_writer.write_frame_yuyv(yuyv_frame.tobytes())
                    except Exception as e:
                        pass

                # Create preview frame (optionally draw face indicator on preview)
                preview_display = processed_frame.copy()
                if self.show_face_box and self.last_face_rect:
                    # If showing face box on preview
                    fx, fy, fw, fh = self.last_face_rect
                    cv2.rectangle(preview_display, (fx, fy), (fx + fw, fy + fh), (0, 255, 128), 2)

                # Encode preview JPEG
                _, jpeg_bytes = cv2.imencode('.jpg', preview_display, [cv2.IMWRITE_JPEG_QUALITY, 80])
                
                with self._lock:
                    self.latest_frame_bgr = processed_frame
                    self.latest_preview_jpeg = jpeg_bytes.tobytes()

                # FPS calculation
                fps_count += 1
                now = time.time()
                if now - fps_timer >= 1.0:
                    self.current_fps = round(fps_count / (now - fps_timer), 1)
                    fps_count = 0
                    fps_timer = now

                # Sleep slightly to match target fps if needed
                time.sleep(0.005)
        finally:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def get_latest_jpeg(self) -> Optional[bytes]:
        """Get latest compressed preview frame JPEG."""
        with self._lock:
            return self.latest_preview_jpeg

    def get_telemetry(self) -> Dict[str, Any]:
        """Get real-time stream status, FPS, zoom level, and framing metrics."""
        return {
            "device": self.device_path,
            "running": self.is_running,
            "fps": self.current_fps,
            "resolution": f"{self.target_width}x{self.target_height}",
            "zoom": round(self.zoom_level, 2),
            "curr_zoom": round(self._curr_zoom, 2),
            "pan_x": round(self.pan_x, 2),
            "pan_y": round(self.pan_y, 2),
            "auto_zoom": self.auto_zoom_enabled,
            "faces_detected": self.detected_faces_count,
            "virtual_cam_active": self.virtual_cam_enabled and (self.loopback_writer is not None and self.loopback_writer.is_open),
            "virtual_device": self.virtual_device_path,
            "flip_horizontal": self.flip_horizontal,
            "background": self.seg_engine.get_status()
        }
