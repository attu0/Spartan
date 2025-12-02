# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import numpy as np
import cv2
from ultralytics import YOLO

app = FastAPI()

# ------------------ CONFIG ------------------
latest_frame = None           # store last uploaded frame
weights = "yolov8n.pt"       # YOLOv8 nano model (CPU-friendly)
conf_thresh = 0.35            # confidence threshold
img_size = 640                # YOLO inference size
show_live = False             # Optional: set True to debug on local window
# --------------------------------------------

# Load YOLO model once
model = YOLO(weights)

# ------------------ UPLOAD ENDPOINT ------------------
@app.post("/upload")
async def upload_frame(file: UploadFile = File(...)):
    """
    Endpoint for Raspberry Pi or any client to upload a single frame.
    """
    global latest_frame
    latest_frame = await file.read()
    return {"status": "ok"}

# ------------------ FRAME GENERATOR ------------------
async def frame_generator():
    """
    Async generator that yields YOLO-processed MJPEG frames.
    """
    global latest_frame
    while True:
        if latest_frame:
            # Convert bytes to OpenCV image
            nparr = np.frombuffer(latest_frame, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Run YOLO detection
            results = model.predict(frame, imgsz=img_size, conf=conf_thresh, verbose=False)
            res = results[0]

            # Draw bounding boxes
            for box, conf, cls in zip(res.boxes.xyxy, res.boxes.conf, res.boxes.cls):
                x1, y1, x2, y2 = map(int, box)
                label = f"{model.names[int(cls)]} {conf:.2f}"

                # Draw rectangle
                cv2.rectangle(frame, (x1, y1), (x2, y2), (14,204,121), 2)

                # Draw label background
                (w,h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1-18), (x1+w, y1), (14,204,121), -1)
                cv2.putText(frame, label, (x1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)

            # Optional: show live on your machine
            if show_live:
                cv2.imshow("YOLO Live", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # Encode frame as JPEG for MJPEG streaming
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpeg.tobytes() +
                    b"\r\n"
                )

        await asyncio.sleep(0.03)  # ~30 FPS

# ------------------ STREAM ENDPOINT ------------------
@app.get("/stream")
async def stream():
    """
    MJPEG streaming endpoint: clients can open in browser <img src="/stream">
    """
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ------------------ FRONTEND ------------------
# Serve static frontend files (optional)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
