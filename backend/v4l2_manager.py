"""
V4L2 Manager - Hardware Camera Controller for Linux
Handles device discovery, capability queries, and V4L2 control get/set operations.
"""

import os
import re
import subprocess
import glob
from typing import Dict, List, Any, Optional

class V4L2Manager:
    def __init__(self):
        self._check_v4l2_ctl()

    def _check_v4l2_ctl(self) -> bool:
        """Check if v4l2-ctl is installed."""
        try:
            res = subprocess.run(["which", "v4l2-ctl"], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all video capture devices with card names and device node paths."""
        devices = []
        try:
            output = subprocess.run(
                ["v4l2-ctl", "--list-devices"],
                capture_output=True,
                text=True,
                check=True
            ).stdout

            current_card = None
            current_bus = None
            nodes = []

            for line in output.splitlines():
                if not line.strip():
                    if current_card and nodes:
                        is_loop = (
                            "loopback" in (current_card or "").lower() or 
                            "virtual" in (current_card or "").lower() or 
                            "controller" in (current_card or "").lower() or
                            "v4l2loopback" in (current_bus or "").lower()
                        )
                        if not is_loop:
                            devices.append({
                                "card": current_card,
                                "bus": current_bus,
                                "nodes": nodes,
                                "primary_node": nodes[0] if nodes else None
                            })
                    current_card = None
                    current_bus = None
                    nodes = []
                    continue

                if not line.startswith("\t") and not line.startswith(" "):
                    # Device card name line e.g., "EasyCam 501: EasyCam 501 (usb-...):"
                    card_info = line.strip().rstrip(":")
                    current_card = card_info
                    if "(" in card_info and ")" in card_info:
                        parts = card_info.rsplit("(", 1)
                        current_card = parts[0].strip()
                        current_bus = parts[1].rstrip(")").strip()
                else:
                    # Node line e.g., "\t/dev/video0"
                    node = line.strip()
                    if node.startswith("/dev/video"):
                        nodes.append(node)

            if current_card and nodes:
                is_loop = (
                    "loopback" in (current_card or "").lower() or 
                    "virtual" in (current_card or "").lower() or 
                    "controller" in (current_card or "").lower() or
                    "v4l2loopback" in (current_bus or "").lower()
                )
                if not is_loop:
                    devices.append({
                        "card": current_card,
                        "bus": current_bus,
                        "nodes": nodes,
                        "primary_node": nodes[0] if nodes else None
                    })
        except Exception as e:
            # Fallback to glob /dev/video*
            for dev_path in sorted(glob.glob("/dev/video*")):
                devices.append({
                    "card": f"Camera ({dev_path})",
                    "bus": "Unknown",
                    "nodes": [dev_path],
                    "primary_node": dev_path
                })

        return devices

    def get_controls(self, device: str) -> Dict[str, Any]:
        """Get all supported V4L2 controls for a given device node."""
        controls: Dict[str, Any] = {}
        if not os.path.exists(device):
            return controls

        try:
            output = subprocess.run(
                ["v4l2-ctl", "-d", device, "-l"],
                capture_output=True,
                text=True,
                check=True
            ).stdout

            current_category = "General"

            # Parse control lines:
            # e.g.: brightness 0x00980900 (int) : min=-64 max=64 step=1 default=0 value=0 flags=...
            # e.g.: auto_exposure 0x009a0901 (menu) : min=0 max=3 default=3 value=3 (Aperture Priority Mode)
            # e.g.: white_balance_automatic 0x0098090c (bool) : default=1 value=1
            for line in output.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue

                if line_str.endswith("Controls"):
                    current_category = line_str
                    continue

                # Match control line
                # Regex for control name, id, type, parameters
                match = re.match(r"^([a-zA-Z0-9_]+)\s+(0x[0-9a-fA-F]+)\s+\(([a-zA-Z]+)\)\s*:\s*(.*)$", line_str)
                if match:
                    ctrl_name = match.group(1)
                    ctrl_id = match.group(2)
                    ctrl_type = match.group(3)
                    params_str = match.group(4)

                    ctrl_data: Dict[str, Any] = {
                        "name": ctrl_name,
                        "id": ctrl_id,
                        "type": ctrl_type,
                        "category": current_category,
                        "flags": [],
                        "min": None,
                        "max": None,
                        "step": 1,
                        "default": None,
                        "value": None,
                        "menu_options": {}
                    }

                    # Extract flags
                    if "flags=" in params_str:
                        flags_part = params_str.split("flags=")[-1].strip()
                        ctrl_data["flags"] = [f.strip() for f in flags_part.split(",")]

                    # Extract min, max, step, default, value
                    min_match = re.search(r"min=(-?\d+)", params_str)
                    if min_match:
                        ctrl_data["min"] = int(min_match.group(1))

                    max_match = re.search(r"max=(-?\d+)", params_str)
                    if max_match:
                        ctrl_data["max"] = int(max_match.group(1))

                    step_match = re.search(r"step=(-?\d+)", params_str)
                    if step_match:
                        ctrl_data["step"] = int(step_match.group(1))

                    default_match = re.search(r"default=(-?\d+)", params_str)
                    if default_match:
                        ctrl_data["default"] = int(default_match.group(1))

                    value_match = re.search(r"value=(-?\d+)", params_str)
                    if value_match:
                        ctrl_data["value"] = int(value_match.group(1))
                    elif ctrl_type == "bool":
                        if "value=1" in params_str:
                            ctrl_data["value"] = 1
                        elif "value=0" in params_str:
                            ctrl_data["value"] = 0

                    ctrl_data["inactive"] = "inactive" in ctrl_data["flags"] or "grabbed" in ctrl_data["flags"]
                    controls[ctrl_name] = ctrl_data

        except Exception as e:
            print(f"[V4L2Manager] Error reading controls for {device}: {e}")

        return controls

    def set_control(self, device: str, control_name: str, value: Any) -> Dict[str, Any]:
        """Set a V4L2 control value."""
        if not os.path.exists(device):
            return {"success": False, "error": f"Device {device} does not exist"}

        try:
            # Check if converting to int/bool is needed
            if isinstance(value, bool):
                val_str = "1" if value else "0"
            else:
                val_str = str(int(value))

            cmd = ["v4l2-ctl", "-d", device, "-c", f"{control_name}={val_str}"]
            res = subprocess.run(cmd, capture_output=True, text=True)

            if res.returncode != 0:
                return {
                    "success": False,
                    "error": res.stderr.strip() or res.stdout.strip(),
                    "control": control_name,
                    "value": value
                }

            return {
                "success": True,
                "control": control_name,
                "value": value
            }
        except Exception as e:
            return {"success": False, "error": str(e), "control": control_name, "value": value}

    def reset_controls(self, device: str) -> Dict[str, Any]:
        """Reset all controls on a device to their defaults."""
        controls = self.get_controls(device)
        results = {}
        for name, data in controls.items():
            if data.get("default") is not None and not data.get("inactive", False):
                res = self.set_control(device, name, data["default"])
                results[name] = res
        return {"success": True, "results": results}

    def get_device_resolutions(self, device: str) -> List[Dict[str, Any]]:
        """Get supported formats and resolutions for a video device."""
        resolutions = []
        try:
            output = subprocess.run(
                ["v4l2-ctl", "--list-formats-ext", "-d", device],
                capture_output=True,
                text=True,
                check=True
            ).stdout

            current_format = None
            for line in output.splitlines():
                line_str = line.strip()
                if line_str.startswith("[") and ":" in line_str:
                    # Format line e.g. [0]: 'MJPG' (Motion-JPEG)
                    current_format = line_str.split("'")[1] if "'" in line_str else "Unknown"
                elif line_str.startswith("Size: Discrete"):
                    size_str = line_str.replace("Size: Discrete", "").strip()
                    if "x" in size_str:
                        w, h = map(int, size_str.split("x"))
                        item = {"format": current_format, "width": w, "height": h}
                        if item not in resolutions:
                            resolutions.append(item)
        except Exception as e:
            print(f"[V4L2Manager] Error reading resolutions for {device}: {e}")
            # Standard fallbacks
            resolutions = [
                {"format": "MJPG", "width": 1920, "height": 1080},
                {"format": "MJPG", "width": 1280, "height": 720},
                {"format": "YUYV", "width": 640, "height": 480}
            ]
        return resolutions
