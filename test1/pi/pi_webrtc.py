# pi_webrtc.py (fixed)
import asyncio
import json
import time
import cv2
import requests
import av
from aiortc import RTCPeerConnection, VideoStreamTrack, RTCSessionDescription
from picamera2 import Picamera2

# <-- set this to your laptop IP (signaling server)
LAPTOP_IP = "10.156.97.118"
SIGNAL_URL = f"http://10.156.97.118:8000"

# Camera setup (1280x720)
picam2 = Picamera2()
config = picam2.create_video_configuration({"size": (1280, 720)})
picam2.configure(config)
picam2.start()
time.sleep(0.5)  # warm-up


class CameraStreamTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that yields frames from Picamera2 as av.VideoFrame.
    """
    def __init__(self):
        super().__init__()

    async def recv(self):
        # Capture array from Picamera2 (BGR)
        frame = picam2.capture_array()

        # Convert BGR -> RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create av.VideoFrame
        av_frame = av.VideoFrame.from_ndarray(frame_rgb, format="rgb24")

        # CORRECT: await next_timestamp() to get pts/time_base
        try:
            pts, time_base = await self.next_timestamp()
            av_frame.pts = pts
            av_frame.time_base = time_base
        except Exception as exc:
            # if something goes wrong, log and raise to stop the track
            print("next_timestamp error:", exc)
            raise

        return av_frame


async def run():
    pc = RTCPeerConnection()
    pc.addTrack(CameraStreamTrack())

    # create local offer and set it
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # send the offer (SDP + type) to the signaling server
    payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    try:
        requests.post(f"{SIGNAL_URL}/offer", json=payload, timeout=5)
        print("Offer posted to signaling server")
    except Exception as e:
        print("Failed to POST offer:", e)
        await pc.close()
        return

    # poll the signaling server for an answer
    print("Waiting for answer...")
    answer = None
    for _ in range(120):  # wait up to ~60 seconds (120 * 0.5s)
        try:
            r = requests.get(f"{SIGNAL_URL}/answer", timeout=3)
            if r.status_code == 200 and r.content:
                try:
                    j = r.json()
                except Exception:
                    j = None
                if j and "sdp" in j and "type" in j:
                    answer = j
                    break
        except Exception:
            pass
        await asyncio.sleep(0.5)

    if not answer:
        print("No answer received (timed out).")
        await pc.close()
        return

    # apply the remote answer
    remote_desc = RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
    await pc.setRemoteDescription(remote_desc)
    print("Remote description set — WebRTC connection established.")

    # keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted — closing peer connection")
    finally:
        await pc.close()


if __name__ == "__main__":
    asyncio.run(run())
