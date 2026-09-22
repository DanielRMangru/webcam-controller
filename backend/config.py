"""
Config & Profiles Manager - Saves and loads camera setting presets.
"""

import os
import json
from typing import Dict, Any, List

CONFIG_DIR = os.path.expanduser("~/.config/webcam-controller")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")

DEFAULT_PROFILES = {
    "Default": {
        "zoom": 1.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
        "auto_zoom": False,
        "v4l2": {
            "brightness": 0,
            "contrast": 35,
            "saturation": 68,
            "gain": 0,
            "gamma": 100,
            "sharpness": 4,
            "auto_exposure": 3,
            "focus_automatic_continuous": 1,
            "white_balance_automatic": 1
        }
    },
    "Meeting Close-up (1.5x)": {
        "zoom": 1.5,
        "pan_x": 0.0,
        "pan_y": -0.15,
        "auto_zoom": False,
        "v4l2": {
            "brightness": 5,
            "contrast": 38,
            "saturation": 70,
            "sharpness": 4
        }
    },
    "Smart Face Track": {
        "zoom": 1.4,
        "pan_x": 0.0,
        "pan_y": 0.0,
        "auto_zoom": True,
        "v4l2": {}
    },
    "Low Light Boost": {
        "zoom": 1.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
        "auto_zoom": False,
        "v4l2": {
            "brightness": 20,
            "gain": 30,
            "gamma": 130,
            "backlight_compensation": 120
        }
    }
}

class ConfigManager:
    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.profiles: Dict[str, Any] = self._load_profiles()

    def _load_profiles(self) -> Dict[str, Any]:
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, "r") as f:
                    data = json.load(f)
                    # Merge defaults if missing
                    for k, v in DEFAULT_PROFILES.items():
                        if k not in data:
                            data[k] = v
                    return data
            except Exception as e:
                print(f"[Config] Error reading profiles: {e}")
        return dict(DEFAULT_PROFILES)

    def save_profile(self, name: str, settings: Dict[str, Any]) -> bool:
        """Save a named profile."""
        self.profiles[name] = settings
        try:
            with open(PROFILES_FILE, "w") as f:
                json.dump(self.profiles, f, indent=2)
            return True
        except Exception as e:
            print(f"[Config] Error saving profile: {e}")
            return False

    def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        if name in self.profiles and name not in DEFAULT_PROFILES:
            del self.profiles[name]
            try:
                with open(PROFILES_FILE, "w") as f:
                    json.dump(self.profiles, f, indent=2)
                return True
            except Exception as e:
                print(f"[Config] Error deleting profile: {e}")
                return False
        return False

    def get_profiles(self) -> Dict[str, Any]:
        return self.profiles
