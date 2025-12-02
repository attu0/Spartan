# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import io
from PIL import Image
import asyncio

app = FastAPI()

latest_frame = None  # store last uploaded frame

@app.post("/upload")
async def upload_frame(file: UploadFile = File(...)):
    global latest_frame
    latest_frame = await file.read()
    return {"status": "ok"}

async def frame_generator():
    global latest_frame
    while True:
        if latest_frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                latest_frame +
                b"\r\n"
            )
        await asyncio.sleep(0.03)  # ~30 FPS
        

@app.get("/stream")
async def stream():
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# Serve frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
#uvicorn main:app --host 0.0.0.0 --port 8000