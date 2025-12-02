# send_frames.py (fixed)
import requests, time, io
from picamera2 import Picamera2
from PIL import Image

LAPTOP_IP = "10.41.175.118"   # <-- put YOUR laptop IP here
UPLOAD_URL = f"http://10.41.175.118:8000/upload"

# Camera setup
picam2 = Picamera2()
#config = picam2.create_video_configuration({"size": (640, 480)})  # lower res also reduces CPU
config = picam2.create_video_configuration({"size": (640, 480)}) #full HD
picam2.configure(config)
picam2.start()
time.sleep(1)  # warm-up

session = requests.Session()
session.headers.update({"User-Agent": "pi-camera-uploader/1.0"})

try:
    while True:
        frame = picam2.capture_array()

        # Convert numpy array -> PIL and ensure RGB (drop alpha if present)
        img = Image.fromarray(frame).convert("RGB")

        buf = io.BytesIO()
        #img.save(buf, format="JPEG", quality=80) 
        img.save(buf, format="JPEG", quality=100)
        buf.seek(0)

        try:
            resp = session.post(UPLOAD_URL, files={"file": ("frame.jpg", buf, "image/jpeg")}, timeout=3)
            if resp.status_code != 200:
                print("Upload returned", resp.status_code)
        except Exception as e:
            print("Upload failed:", e)

        # control frame rate; 0.05 ~ 20 FPS, 0.1 ~ 10 FPS
        time.sleep(0.07)

except KeyboardInterrupt:
    print("Stopping...")
finally:
    try:
        picam2.stop()
    except Exception:
        pass
