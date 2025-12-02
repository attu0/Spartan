import cv2
from ultralytics import YOLO

# ----- CONFIG -----
input_video = r"F:\Spartan\yolo\test.mp4"   # Use raw string to avoid \ issues
output_video = "output.mp4"                 # output file
weights = "yolov8n.pt"                      # YOLOv8 nano pretrained model
conf_thresh = 0.35                           # confidence threshold
img_size = 640                               # YOLO inference size
show_live = True                             # True to show live video
# -------------------

# Load YOLO model
model = YOLO(weights)

# Open video
cap = cv2.VideoCapture(input_video)
if not cap.isOpened():
    raise RuntimeError(f"Could not open video: {input_video}")

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"Video: {input_video}, {width}x{height}, {fps:.2f} FPS, {frame_count} frames")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO inference
    results = model.predict(frame, imgsz=img_size, conf=conf_thresh, verbose=False)
    res = results[0]

    # Draw boxes on frame
    for box, conf, cls in zip(res.boxes.xyxy, res.boxes.conf, res.boxes.cls):
        x1, y1, x2, y2 = map(int, box)
        label = f"{model.names[int(cls)]} {conf:.2f}"
        # rectangle
        cv2.rectangle(frame, (x1, y1), (x2, y2), (14,204,121), 2)
        # label background
        (w,h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, y1-18), (x1+w, y1), (14,204,121), -1)
        cv2.putText(frame, label, (x1, y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1)

    # write frame
    out.write(frame)

    # show live
    if show_live:
        cv2.imshow("YOLO Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Interrupted by user")
            break

cap.release()
out.release()
cv2.destroyAllWindows()
print(f"Done! Output saved to {output_video}")
