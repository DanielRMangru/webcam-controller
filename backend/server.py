"""
Webcam Controller Server - FastAPI application providing REST API,
WebSocket telemetry, live MJPEG video preview, and static UI serving.
"""

import os
import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .v4l2_manager import V4L2Manager
from .stream_engine import StreamEngine
from .loopback_helper import LoopbackManager
from .config import ConfigManager

app = FastAPI(title="Linux Webcam Controller", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
v4l2_mgr = V4L2Manager()
config_mgr = ConfigManager()
active_device = "/dev/video0"

# Initial devices check
devices = v4l2_mgr.list_devices()
if devices and devices[0].get("primary_node"):
    active_device = devices[0]["primary_node"]

stream_engine = StreamEngine(device_path=active_device, target_width=1280, target_height=720, target_fps=30)
stream_engine.start()

# WebSocket clients
connected_websockets = set()

# Models
class SetControlRequest(BaseModel):
    name: str
    value: Any

class SetZoomRequest(BaseModel):
    zoom: float
    pan_x: Optional[float] = None
    pan_y: Optional[float] = None

class SetPanTiltRequest(BaseModel):
    pan_x: float
    pan_y: float

class SetAutoZoomRequest(BaseModel):
    enabled: bool
    smoothing: Optional[float] = 0.12

class SelectDeviceRequest(BaseModel):
    device: str

class ToggleVirtualCamRequest(BaseModel):
    enabled: bool
    device: Optional[str] = None

class SaveProfileRequest(BaseModel):
    name: str
    settings: Dict[str, Any]

class ApplyProfileRequest(BaseModel):
    name: str

class ToggleMirrorRequest(BaseModel):
    flip: bool


# Background telemetry broadcaster
async def broadcast_telemetry():
    while True:
        try:
            if connected_websockets:
                telemetry = stream_engine.get_telemetry()
                telemetry["active_device"] = active_device
                msg = json.dumps({"type": "telemetry", "data": telemetry})
                dead_sockets = set()
                for ws in connected_websockets:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead_sockets.add(ws)
                connected_websockets.difference_update(dead_sockets)
        except Exception:
            pass
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_telemetry())

@app.on_event("shutdown")
def shutdown_event():
    stream_engine.stop()

# --- API Endpoints ---

@app.get("/api/devices")
def get_devices():
    """List all available video capture devices."""
    devs = v4l2_mgr.list_devices()
    resolutions = v4l2_mgr.get_device_resolutions(active_device)
    return {
        "active_device": active_device,
        "devices": devs,
        "resolutions": resolutions
    }

@app.post("/api/devices/select")
def select_device(req: SelectDeviceRequest):
    """Switch the active camera device."""
    global active_device
    active_device = req.device
    success = stream_engine.set_camera_device(active_device)
    return {"success": success, "active_device": active_device}

@app.get("/api/controls")
def get_controls():
    """Get all V4L2 hardware controls for current device."""
    ctrls = v4l2_mgr.get_controls(active_device)
    return {
        "device": active_device,
        "controls": ctrls
    }

@app.post("/api/controls")
def set_control(req: SetControlRequest):
    """Set a hardware V4L2 control value."""
    res = v4l2_mgr.set_control(active_device, req.name, req.value)
    return res

@app.post("/api/controls/reset")
def reset_controls():
    """Reset all hardware controls to default."""
    res = v4l2_mgr.reset_controls(active_device)
    return res

@app.post("/api/zoom")
def set_zoom(req: SetZoomRequest):
    """Set digital zoom and optional pan/tilt."""
    stream_engine.set_zoom(req.zoom, req.pan_x, req.pan_y)
    
    # Check if hardware zoom exists on this camera as well
    ctrls = v4l2_mgr.get_controls(active_device)
    if "zoom_absolute" in ctrls:
        z_min = ctrls["zoom_absolute"].get("min", 1)
        z_max = ctrls["zoom_absolute"].get("max", 10)
        # Map 1.0-5.0 to hw range
        hw_val = int(z_min + (req.zoom - 1.0) / 4.0 * (z_max - z_min))
        v4l2_mgr.set_control(active_device, "zoom_absolute", hw_val)

    return {"success": True, "zoom": stream_engine.zoom_level}

@app.post("/api/pan-tilt")
def set_pan_tilt(req: SetPanTiltRequest):
    """Set digital pan and tilt coordinates (-1.0 to 1.0)."""
    stream_engine.set_pan_tilt(req.pan_x, req.pan_y)
    return {"success": True, "pan_x": stream_engine.pan_x, "pan_y": stream_engine.pan_y}

@app.post("/api/auto-zoom")
def set_auto_zoom(req: SetAutoZoomRequest):
    """Toggle face-tracking auto-zoom."""
    stream_engine.set_auto_zoom(req.enabled, req.smoothing)
    return {"success": True, "auto_zoom": stream_engine.auto_zoom_enabled}

@app.post("/api/mirror")
def toggle_mirror(req: ToggleMirrorRequest):
    """Toggle horizontal preview flip."""
    stream_engine.flip_horizontal = req.flip
    return {"success": True, "flip_horizontal": stream_engine.flip_horizontal}

@app.get("/api/virtual-cam/status")
def get_virtual_cam_status():
    """Get status of v4l2loopback module and virtual device."""
    status = LoopbackManager.get_status()
    status["active"] = stream_engine.virtual_cam_enabled and (
        stream_engine.loopback_writer is not None and stream_engine.loopback_writer.is_open
    )
    status["current_device"] = stream_engine.virtual_device_path
    return status

@app.post("/api/virtual-cam/toggle")
def toggle_virtual_cam(req: ToggleVirtualCamRequest):
    """Start or stop outputting to virtual camera loopback device."""
    res = stream_engine.set_virtual_cam(req.enabled, req.device)
    return res

@app.get("/api/profiles")
def get_profiles():
    """Get all saved profiles."""
    return config_mgr.get_profiles()

@app.post("/api/profiles/save")
def save_profile(req: SaveProfileRequest):
    """Save a profile preset."""
    success = config_mgr.save_profile(req.name, req.settings)
    return {"success": success, "name": req.name}

@app.post("/api/profiles/apply")
def apply_profile(req: ApplyProfileRequest):
    """Apply a profile preset."""
    profiles = config_mgr.get_profiles()
    if req.name not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    prof = profiles[req.name]
    # Apply zoom & framing
    if "zoom" in prof:
        stream_engine.set_zoom(prof["zoom"], prof.get("pan_x", 0.0), prof.get("pan_y", 0.0))
    if "auto_zoom" in prof:
        stream_engine.set_auto_zoom(prof["auto_zoom"])
    # Apply hardware controls
    if "v4l2" in prof:
        for ctrl_name, val in prof["v4l2"].items():
            v4l2_mgr.set_control(active_device, ctrl_name, val)

    return {"success": True, "profile": prof}

@app.delete("/api/profiles/{name}")
def delete_profile(name: str):
    """Delete a custom profile."""
    success = config_mgr.delete_profile(name)
    return {"success": success}

# Live MJPEG Stream generator
def generate_mjpeg_frames():
    import time
    while True:
        frame_bytes = stream_engine.get_latest_jpeg()
        if frame_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033) # ~30 FPS

@app.get("/api/video_feed")
def video_feed():
    """Live preview video feed using MJPEG streaming."""
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# WebSocket endpoint for real-time bi-directional control & telemetry
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            action = data.get("action")
            
            if action == "set_zoom":
                stream_engine.set_zoom(data.get("zoom", 1.0), data.get("pan_x"), data.get("pan_y"))
            elif action == "set_pan_tilt":
                stream_engine.set_pan_tilt(data.get("pan_x", 0.0), data.get("pan_y", 0.0))
            elif action == "set_auto_zoom":
                stream_engine.set_auto_zoom(data.get("enabled", False))
            elif action == "set_control":
                v4l2_mgr.set_control(active_device, data.get("name"), data.get("value"))
    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
    except Exception:
        connected_websockets.discard(websocket)

# Serve Frontend static assets
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
