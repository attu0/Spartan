"""Helpers shared by the node and the calibration tools."""
import glob
import os


def find_cam(name="CCB Camera"):
    """Return the capture node (/dev/videoN) of the stereo camera, found by name."""
    for d in sorted(glob.glob("/sys/class/video4linux/video*")):
        try:
            with open(d + "/name") as f:
                cam_name = f.read()
            with open(d + "/index") as f:
                index = f.read().strip()
        except OSError:
            continue
        if name in cam_name and index == "0":
            return "/dev/" + os.path.basename(d)
    raise RuntimeError(
        "stereo camera not found - check `lsusb | grep -i ccb` and `v4l2-ctl --list-devices`")


def open_stereo(cv2, device=-1, eye_w=1280, eye_h=720, fps=30):
    """Open the camera in the side-by-side MJPG mode (2*eye_w x eye_h)."""
    dev = find_cam() if device is None or int(device) < 0 else int(device)
    cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, eye_w * 2)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, eye_h)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {dev} (is another program using the camera?)")
    return cap, dev
