"""
Segmentation Engine - Virtual Backgrounds, Background Blurring,
AI Selfie Segmentation (MediaPipe XNNPACK), and Chroma Keying (Green Screen).
"""

import os
import cv2
import time
import glob
import numpy as np
from typing import Optional, Dict, Any, Tuple

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    Interpreter = None

class SegmentationEngine:
    def __init__(self, target_width: int = 1280, target_height: int = 720):
        self.target_width = target_width
        self.target_height = target_height

        # Settings
        self.enabled = False
        self.mode = "none" # "none", "ai_blur", "ai_image", "ai_color", "chroma_blur", "chroma_image", "chroma_color"
        self.blur_radius = 25 # 5 to 51
        self.solid_color = [0, 0, 0] # [R, G, B]
        self.active_image_name = "office.jpg"

        # Chroma Key (Green / Blue screen) parameters
        self.chroma_color = [0, 255, 0] # [R, G, B]
        self.chroma_similarity = 0.35   # 0.1 to 0.8
        self.chroma_smoothness = 0.10   # 0.01 to 0.3
        self.chroma_spill = 0.40        # 0.0 to 1.0

        # AI Segmentation Model
        self.interpreter: Optional[Any] = None
        self.input_details = None
        self.output_details = None
        self._init_ai_model()

        # Background images directory & cache
        self.bg_dir = os.path.join(os.path.dirname(__file__), "assets", "backgrounds")
        os.makedirs(self.bg_dir, exist_ok=True)
        self._bg_cache: Dict[str, np.ndarray] = {}
        self._load_preset_images()

    def _init_ai_model(self):
        """Initialize Google MediaPipe Selfie Segmenter model via LiteRT."""
        model_path = os.path.join(os.path.dirname(__file__), "models", "selfie_segmenter.tflite")
        if os.path.exists(model_path) and Interpreter is not None:
            try:
                self.interpreter = Interpreter(model_path=model_path)
                self.interpreter.allocate_tensors()
                self.input_details = self.interpreter.get_input_details()
                self.output_details = self.interpreter.get_output_details()
                print(f"[SegmentationEngine] AI Selfie Segmenter initialized from {model_path}")
            except Exception as e:
                print(f"[SegmentationEngine] Error initializing AI segmenter: {e}")
                self.interpreter = None

    def _load_preset_images(self):
        """Preload and cache background images."""
        for p in glob.glob(os.path.join(self.bg_dir, "*.*")):
            fname = os.path.basename(p)
            try:
                img = cv2.imread(p)
                if img is not None:
                    img_resized = cv2.resize(img, (self.target_width, self.target_height), interpolation=cv2.INTER_LINEAR)
                    self._bg_cache[fname] = img_resized
            except Exception as e:
                print(f"[SegmentationEngine] Error loading bg image {fname}: {e}")

    def get_preset_list(self) -> list:
        """List available background images."""
        presets = []
        for p in sorted(glob.glob(os.path.join(self.bg_dir, "*.*"))):
            fname = os.path.basename(p)
            presets.append({
                "id": fname,
                "name": os.path.splitext(fname)[0].replace("_", " ").title(),
                "url": f"/api/background/image/{fname}"
            })
        return presets

    def set_config(self, mode: Optional[str] = None, blur_radius: Optional[int] = None,
                   image_name: Optional[str] = None, solid_color: Optional[list] = None,
                   chroma_color: Optional[list] = None, chroma_similarity: Optional[float] = None,
                   chroma_smoothness: Optional[float] = None, chroma_spill: Optional[float] = None):
        """Update segmentation settings."""
        if mode is not None:
            self.mode = mode
            self.enabled = (mode != "none")
        if blur_radius is not None:
            r = int(blur_radius)
            if r % 2 == 0: r += 1
            self.blur_radius = max(3, min(65, r))
        if image_name is not None:
            self.active_image_name = image_name
            # Ensure it is in cache
            if image_name not in self._bg_cache:
                img_path = os.path.join(self.bg_dir, image_name)
                if os.path.exists(img_path):
                    img = cv2.imread(img_path)
                    if img is not None:
                        self._bg_cache[image_name] = cv2.resize(img, (self.target_width, self.target_height))
        if solid_color is not None:
            self.solid_color = solid_color
        if chroma_color is not None:
            self.chroma_color = chroma_color
        if chroma_similarity is not None:
            self.chroma_similarity = float(chroma_similarity)
        if chroma_smoothness is not None:
            self.chroma_smoothness = float(chroma_smoothness)
        if chroma_spill is not None:
            self.chroma_spill = float(chroma_spill)

    def _get_background_frame(self, original_frame_bgr: np.ndarray, bg_type: str) -> np.ndarray:
        """Generate or retrieve the replacement background frame."""
        h, w = original_frame_bgr.shape[:2]

        if bg_type == "blur":
            ksize = self.blur_radius if self.blur_radius % 2 == 1 else self.blur_radius + 1
            return cv2.GaussianBlur(original_frame_bgr, (ksize, ksize), 0)
        
        elif bg_type == "image":
            if self.active_image_name in self._bg_cache:
                bg = self._bg_cache[self.active_image_name]
                if bg.shape[:2] == (h, w):
                    return bg
                return cv2.resize(bg, (w, h))
            else:
                # Fallback blur if image not found
                return cv2.GaussianBlur(original_frame_bgr, (35, 35), 0)

        elif bg_type == "color":
            # Solid color [R, G, B] -> BGR
            r, g, b = self.solid_color
            bg = np.full((h, w, 3), [b, g, r], dtype=np.uint8)
            return bg

        return original_frame_bgr

    def _ai_segment(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Run AI Selfie Segmentation and return single-channel float alpha mask [0.0, 1.0]."""
        if self.interpreter is None:
            # Fallback center oval mask
            h, w = frame_bgr.shape[:2]
            mask = np.ones((h, w), dtype=np.float32)
            return mask

        # Resize to 256x256 for model input
        rgb_small = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb_256 = cv2.resize(rgb_small, (256, 256), interpolation=cv2.INTER_LINEAR)
        input_data = (rgb_256.astype(np.float32) / 255.0)[np.newaxis, ...]

        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        raw_mask = self.interpreter.get_tensor(self.output_details[0]['index'])[0, :, :, 0]

        # Upscale mask back to full resolution
        h, w = frame_bgr.shape[:2]
        full_mask = cv2.resize(raw_mask, (w, h), interpolation=cv2.INTER_LINEAR)
        
        # Soft contrast threshold for cleaner edges
        full_mask = np.clip((full_mask - 0.35) / 0.35, 0.0, 1.0)
        # Apply slight blur to mask to soften edges
        full_mask = cv2.GaussianBlur(full_mask, (5, 5), 0)
        return full_mask

    def _chroma_key_segment(self, frame_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Perform Green / Blue Screen Chroma Keying and Spill Suppression."""
        h, w = frame_bgr.shape[:2]
        # Target key color [R, G, B]
        kr, kg, kb = self.chroma_color

        # Convert to Lab or normalized YCrCb for high color accuracy
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        key_norm = np.array([kr, kg, kb], dtype=np.float32) / 255.0

        # Euclidean distance in RGB color space
        diff = frame_rgb - key_norm
        dist = np.sqrt(np.sum(diff ** 2, axis=2)) # Distance 0.0 to ~1.73

        # Similarity threshold & smoothness feathering
        t_low = max(0.01, self.chroma_similarity - self.chroma_smoothness)
        t_high = min(1.5, self.chroma_similarity + self.chroma_smoothness)

        # Foreground alpha mask (0 = key background, 1 = person)
        alpha = np.clip((dist - t_low) / (t_high - t_low), 0.0, 1.0)
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)

        # Spill Suppression (neutralize green/blue bounce on edges)
        cleaned_bgr = frame_bgr.copy()
        if self.chroma_spill > 0.05:
            # If green screen
            if kg > kr and kg > kb:
                # Green spill suppression: clamp green channel to avg of red & blue
                r_ch = cleaned_bgr[:, :, 2].astype(np.float32)
                g_ch = cleaned_bgr[:, :, 1].astype(np.float32)
                b_ch = cleaned_bgr[:, :, 0].astype(np.float32)
                max_g = (r_ch + b_ch) / 2.0
                excess_g = np.maximum(0, g_ch - max_g) * self.chroma_spill
                cleaned_bgr[:, :, 1] = np.clip(g_ch - excess_g, 0, 255).astype(np.uint8)
            # If blue screen
            elif kb > kr and kb > kg:
                r_ch = cleaned_bgr[:, :, 2].astype(np.float32)
                g_ch = cleaned_bgr[:, :, 1].astype(np.float32)
                b_ch = cleaned_bgr[:, :, 0].astype(np.float32)
                max_b = (r_ch + g_ch) / 2.0
                excess_b = np.maximum(0, b_ch - max_b) * self.chroma_spill
                cleaned_bgr[:, :, 0] = np.clip(b_ch - excess_b, 0, 255).astype(np.uint8)

        return alpha, cleaned_bgr

    def process_frame(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Process incoming frame with virtual background / blur / chroma keying."""
        if not self.enabled or self.mode == "none":
            return frame_bgr

        # Parse mode: e.g. "ai_blur", "ai_image", "chroma_blur", "chroma_image"
        parts = self.mode.split("_")
        seg_type = parts[0] # "ai" or "chroma"
        bg_type = parts[1] if len(parts) > 1 else "blur" # "blur", "image", "color"

        # Generate replacement background frame
        bg_frame = self._get_background_frame(frame_bgr, bg_type)

        # Compute alpha mask
        if seg_type == "chroma":
            alpha, subject_frame = self._chroma_key_segment(frame_bgr)
        else: # AI Segmentation
            alpha = self._ai_segment(frame_bgr)
            subject_frame = frame_bgr

        # 3-channel alpha expansion
        alpha_3d = alpha[:, :, np.newaxis]

        # Alpha composite: Result = Subject * alpha + Background * (1 - alpha)
        composite = (subject_frame.astype(np.float32) * alpha_3d +
                     bg_frame.astype(np.float32) * (1.0 - alpha_3d))
        
        return np.clip(composite, 0, 255).astype(np.uint8)

    def get_status(self) -> Dict[str, Any]:
        """Get current background segmentation telemetry & settings."""
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "blur_radius": self.blur_radius,
            "active_image": self.active_image_name,
            "solid_color": self.solid_color,
            "chroma_color": self.chroma_color,
            "chroma_similarity": self.chroma_similarity,
            "chroma_smoothness": self.chroma_smoothness,
            "chroma_spill": self.chroma_spill,
            "ai_available": self.interpreter is not None
        }
