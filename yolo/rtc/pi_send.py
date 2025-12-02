import asyncio
import requests
import time
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

# CONFIG
LAPTOP_IP = "10.41.175.118" # Your Laptop IP
SIGNALING_URL = f"http://{LAPTOP_IP}:8000/offer"

async def run():
    # 1. Open the Camera
    # 'default:0' usually maps to /dev/video0. 
    # format='v4l2' uses the native Video4Linux driver (very fast).
    # options allow requesting specific resolution/framerate from the hardware.
    player = MediaPlayer('/dev/video0', format='v4l2', options={
        "video_size": "640x480",
        "framerate": "30"
    })
    
    pc = RTCPeerConnection()
    
    # Add the video track to the connection
    pc.addTrack(player.video)

    # 2. Create the Offer (Signaling)
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # 3. Send Offer to Laptop (via HTTP)
    print("Sending offer to laptop...")
    payload = {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }
    
    try:
        response = requests.post(SIGNALING_URL, json=payload)
        res_data = response.json()
    except Exception as e:
        print(f"Could not connect to laptop: {e}")
        return

    # 4. Receive Answer from Laptop
    answer = RTCSessionDescription(sdp=res_data["sdp"], type=res_data["type"])
    await pc.setRemoteDescription(answer)
    print("Connection established! Streaming video...")

    # Keep the script running to maintain the stream
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await pc.close()

if __name__ == "__main__":
    asyncio.run(run())
    