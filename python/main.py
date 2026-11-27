import threading
import time
import random
import datetime

import psutil

from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.dbstorage_tsstore import TimeSeriesStore

# Bridge talks to the sketch on the MCU. If it is missing or the sketch does not
# provide these functions yet, calls are logged and skipped instead of crashing.
try:
    from arduino.app_utils import Bridge
except Exception:
    Bridge = None

web_ui = WebUI()
db = TimeSeriesStore()

WATCHDOG_S = 0.5          # stop rover if no "drive" for this long
SPRAY_MAX_LINEAR = 0.05   # only spray while (almost) stationary
MAX_SPRAY_MS = 5000

state = {
    "linear": 0.0,        # -1..1, + forward
    "angular": 0.0,       # -1..1, + left
    "last_cmd": 0.0,
    "arm": [90, 115, 75], # base, shoulder, elbow (deg)
    "spraying": False,
}
lock = threading.Lock()


# ---------------- MCU helpers ----------------
def mcu(fn, *args):
    """Call a function provided by the sketch (Bridge.provide on the MCU side)."""
    if Bridge is None:
        return
    try:
        Bridge.call(fn, *args)
    except Exception as e:
        log(f"MCU '{fn}' failed: {e}")


def log(msg):
    print(msg, flush=True)
    web_ui.send_message("log", msg)


def _dir_from_val(val, deadband=0.15):
    if val > deadband:
        return 1
    if val < -deadband:
        return -1
    return 0


def wheel_speeds(linear, angular):
    """Differential drive mix -> (left, right) in -1..1."""
    left = max(-1.0, min(1.0, linear - angular * 0.7))
    right = max(-1.0, min(1.0, linear + angular * 0.7))
    return left, right


def apply_drive():
    left, right = wheel_speeds(state["linear"], state["angular"])
    mcu("set_motor_x", _dir_from_val(left))
    mcu("set_motor_y", _dir_from_val(right))


def stop_motors():
    state["linear"] = state["angular"] = 0.0
    mcu("stop_motor_x")
    mcu("stop_motor_y")


# ---------------- Socket handlers ----------------
def on_drive(sid, data):
    with lock:
        state["linear"] = max(-1.0, min(1.0, float(data.get("linear", 0))))
        state["angular"] = max(-1.0, min(1.0, float(data.get("angular", 0))))
        state["last_cmd"] = time.time()
        apply_drive()


def on_estop(sid, data):
    with lock:
        stop_motors()
        mcu("stop_all")
    set_pump(False)
    log("E-STOP")


def on_arm(sid, data):
    joints = data.get("joints", [])
    if len(joints) != 3:
        return
    base, shoulder, elbow = (int(j) for j in joints)
    # Clamp to the same limits the UI sliders use
    base = max(0, min(180, base))
    shoulder = max(25, min(160, shoulder))
    elbow = max(20, min(160, elbow))
    prev_shoulder = state["arm"][1]
    state["arm"] = [base, shoulder, elbow]

    delta_s = shoulder - prev_shoulder
    if delta_s > 0:
        mcu("set_joint_za", 1)
    elif delta_s < 0:
        mcu("set_joint_za", -1)
    else:
        mcu("stop_joint_za")

    mcu("set_servo_angle", elbow)


def set_pump(on):
    state["spraying"] = on
    if on:
        log("Pump state ON (no MCU pump bridge handler registered)")


def spray_for(ms):
    ms = min(int(ms), MAX_SPRAY_MS)
    if ms <= 0:
        return
    if abs(state["linear"]) > SPRAY_MAX_LINEAR:
        log("Spray skipped: rover is moving")
        return

    def run():
        set_pump(True)
        log(f"Pump ON for {ms} ms")
        t_end = time.time() + ms / 1000
        while time.time() < t_end:
            if not state["spraying"]:           # cancelled by E-STOP
                return
            if abs(state["linear"]) > SPRAY_MAX_LINEAR:
                log("Pump OFF: rover started moving")
                break
            time.sleep(0.05)
        set_pump(False)

    threading.Thread(target=run, daemon=True).start()


# ---------------- Leaf inference ----------------
CLASSES = {
    "early_blight":   {"title": "Early Blight",    "spray_ms": 2500},
    "powdery_mildew": {"title": "Powdery Mildew",  "spray_ms": 2200},
    "healthy":        {"title": "Healthy Leaf",    "spray_ms": 0},
}
_demo_idx = 0


def run_inference(source, image_b64, sample_hint=None):
    """
    TODO: replace with the real CNN.
      source      : "arm_camera" | "upload"
      image_b64   : data-URL JPEG (224x224) for "upload", None for "arm_camera"
                    (grab the frame from the board camera yourself in that case)
      sample_hint : the Blight/Mildew/Healthy button selected in the UI. Demo only:
                    the stub honours it, a real model must ignore it.
    Return probabilities in this order: early blight, late blight, powdery mildew, healthy.
    This stub cycles through demo results so the whole pipeline can be tested.
    """
    global _demo_idx
    if sample_hint in CLASSES:
        key = sample_hint
    else:
        key = list(CLASSES)[_demo_idx % len(CLASSES)]
        _demo_idx += 1
    top = round(random.uniform(90, 98), 1)
    rest = round(100 - top, 1)
    probs = {"eb": 0.0, "lb": 0.0, "pm": 0.0, "hl": 0.0}
    top_key = {"early_blight": "eb", "powdery_mildew": "pm", "healthy": "hl"}[key]
    others = [k for k in probs if k != top_key]
    split = [round(rest * w, 1) for w in (0.5, 0.3, 0.2)]
    probs[top_key] = top
    for k, v in zip(others, split):
        probs[k] = v
    time.sleep(0.8)   # fake model latency
    return key, top, probs


def on_cnn_predict(sid, data):
    def work():
        key, conf, probs = run_inference(
            data.get("source", "arm_camera"), data.get("image"), data.get("sample"))
        info = CLASSES[key]
        web_ui.send_message("cnn_result", {
            "sample": key,
            "title": info["title"],
            "conf": conf,
            "probs": probs,
            "sprayMs": info["spray_ms"],
        })
        log(f"CNN: {info['title']} {conf}%")
        if info["spray_ms"] > 0:
            spray_for(info["spray_ms"])

    threading.Thread(target=work, daemon=True).start()


for name, fn in [("drive", on_drive), ("estop", on_estop), ("arm", on_arm),
                 ("cnn_predict", on_cnn_predict)]:
    web_ui.on_message(name, fn)


# ---------------- GPS ----------------
def read_gps():
    """TODO: read the NEO-6M (serial/NMEA or via the sketch).
    Return {"fix": True, "lat": ..., "lon": ...} when you have a fix."""
    return {"fix": False}


# ---------------- System resources logger ----------------
# Samples CPU / memory every ~5 s, stores them in the time-series DB, pushes live
# values to the browser and serves history for the 1 h / 1 D charts.
def on_get_samples(resource: str, start: str, aggr_window: str):
    try:
        samples = db.read_samples(measure=resource, start_from=start,
                                  aggr_window=aggr_window, aggr_func="mean", limit=100)
        return [{"ts": s[1], "value": s[2]} for s in samples]
    except Exception as e:
        print(f"get_samples failed: {e}", flush=True)
        return []


web_ui.expose_api("GET", "/get_samples/{resource}/{start}/{aggr_window}", on_get_samples)


def resources_loop():
    while True:
        try:
            ts = int(datetime.datetime.now().timestamp() * 1000)
            cpu = psutil.cpu_percent(interval=1)
            vm = psutil.virtual_memory()
            try:
                db.write_sample("cpu", cpu, ts)
                db.write_sample("mem", vm.percent, ts)
            except Exception:
                pass
            web_ui.send_message("cpu_usage", {"value": cpu, "ts": ts})
            web_ui.send_message("memory_usage", {
                "value": vm.percent, "ts": ts,
                "used_gb": (vm.total - vm.available) / 1024 ** 3,
                "total_gb": vm.total / 1024 ** 3,
            })
        except Exception as e:
            print(f"resources_loop error: {e}", flush=True)
        time.sleep(4)


threading.Thread(target=resources_loop, daemon=True).start()


# ---------------- Telemetry + watchdog ----------------
def telemetry_loop():
    while True:
        with lock:
            # Safety: stop if the browser stops sending commands
            if (state["linear"] or state["angular"]) and time.time() - state["last_cmd"] > WATCHDOG_S:
                stop_motors()
                log("Watchdog: no commands, motors stopped")
            left, right = wheel_speeds(state["linear"], state["angular"])
        web_ui.send_message("telemetry", {
            "battery": 87,                    # TODO: real reading
            "heading": 0,                     # TODO: IMU / compass
            "gps": read_gps(),
            "rpm": [round(left * 130), round(right * 130)],   # estimate from command
            "spraying": state["spraying"],
        })
        time.sleep(0.5)


threading.Thread(target=telemetry_loop, daemon=True).start()

App.run()