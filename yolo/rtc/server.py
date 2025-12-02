import asyncio
import cv2
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from ultralytics import YOLO
import numpy as np

app = FastAPI()

# Load Model Once
model = YOLO("yolov8n.pt")

class ObjectDetectionTrack(VideoStreamTrack):
    """
    This track receives video frames from the Pi,
    runs YOLO, and (optionally) displays them.
    """
    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        # 1. Get the frame from the Pi (Low Latency UDP)
        frame = await self.track.recv()
        
        # 2. Convert to numpy array (OpenCV format)
        img = frame.to_ndarray(format="bgr24")

        # 3. Run YOLO Object Detection
        results = model.predict(img, conf=0.5, verbose=False)
        
        # 4. Draw Bounding Boxes
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                label = f"{model.names[int(box.cls[0])]} {float(box.conf[0]):.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 5. Display the frame LIVE on the Laptop
        # Note: cv2.imshow inside async can be tricky on some OS (Mac). 
        # If it freezes, we might need a separate thread, but this works on most Linux/Windows.
        cv2.imshow("YOLO Real-Time (WebRTC)", img)
        cv2.waitKey(1)

        # Return the frame (if we wanted to send it back, but we are just displaying here)
        # We must return the frame to keep the pipeline moving.
        return frame

@app.post("/offer")
async def offer(request: Request):
    """
    Signaling Endpoint: The Pi sends its configuration (SDP Offer) here.
    We reply with our configuration (SDP Answer).
    """
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    
    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            print("Video track received! Starting YOLO...")
            # Wrap the incoming track with our processing logic
            local_video = ObjectDetectionTrack(track)
            # We add the track back to the PC (optional, if we were sending it back)
            pc.addTrack(local_video)

    # Set the remote description (what the Pi supports)
    await pc.setRemoteDescription(offer)
    
    # Create answer (what we support)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JSONResponse({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

# Run with: uvicorn server:app --host 0.0.0.0 --port 8000