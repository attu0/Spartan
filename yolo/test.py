from ultralytics import YOLO
import cv2
import torch

print("YOLO ready")
print("OpenCV:", cv2.__version__)
print("Torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
