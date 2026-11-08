#!/usr/bin/env python3
"""AR0144 stereo camera -> ROS 2 (Jazzy).

Publishes (frame: stereo_optical_frame, x right / y down / z forward):
  stereo/left/image_rect   stereo/left/camera_info
  stereo/right/image_rect  stereo/right/camera_info
  stereo/depth_color       colormapped disparity (for quick viewing)
  stereo/points            sensor_msgs/PointCloud2, xyz + rgb, metres
"""
import os
import time

import cv2
import numpy as np
import rclpy
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image, PointCloud2, PointField

from spartan_depth_cam.utils import open_stereo


class StereoNode(Node):
    def __init__(self):
        super().__init__("stereo_node")
        dp = self.declare_parameter
        calib = dp("calib", "").value or os.path.join(
            get_package_share_directory("spartan_depth_cam"), "config", "stereo_calib.npz")
        device = int(dp("device", -1).value)          # -1 = find "CCB Camera" by name
        self.s = float(dp("scale", 0.25).value)       # processing scale, 1.0 = full res
        self.nd = int(dp("num_disp", 32).value)       # multiple of 16
        self.st = int(dp("stride", 1).value)          # point-cloud decimation
        self.zmin = float(dp("z_min", 0.3).value)
        self.zmax = float(dp("z_max", 5.0).value)
        self.frame = dp("frame_id", "stereo_optical_frame").value
        self.min_dt = 1.0 / float(dp("max_rate", 10.0).value)
        self.last = 0.0

        if not os.path.isfile(calib):
            raise FileNotFoundError(
                f"calibration file not found: {calib}\n"
                "Copy stereo_calib.npz into src/spartan_depth_cam/config/ and rebuild, "
                "or pass -p calib:=/path/to/stereo_calib.npz")
        c = np.load(calib)
        self.W, self.H = (int(v) for v in c["size"])   # one eye, e.g. 1280x720
        s = self.s
        self.w, self.h = int(self.W * s), int(self.H * s)

        def scaled(M):
            M = M.copy()
            M[:2] *= s
            return M

        K1s, K2s, P1s, P2s = scaled(c["K1"]), scaled(c["K2"]), scaled(c["P1"]), scaled(c["P2"])
        size = (self.w, self.h)
        self.ml = cv2.initUndistortRectifyMap(K1s, c["D1"], c["R1"], P1s, size, cv2.CV_16SC2)
        self.mr = cv2.initUndistortRectifyMap(K2s, c["D2"], c["R2"], P2s, size, cv2.CV_16SC2)
        self.f, self.cx, self.cy = P1s[0, 0], P1s[0, 2], P1s[1, 2]
        self.B = -P2s[0, 3] / P2s[0, 0]                 # baseline in metres
        self.info_l, self.info_r = self.make_info(P1s), self.make_info(P2s)
        self.get_logger().info(
            f"{self.w}x{self.h} per eye, baseline {self.B:.4f} m, f {self.f:.1f}px, "
            f"max {1.0 / self.min_dt:.1f} Hz")

        bs = 5
        self.sgbm = cv2.StereoSGBM_create(
            minDisparity=0, numDisparities=self.nd, blockSize=bs,
            P1=8 * 3 * bs * bs, P2=32 * 3 * bs * bs, disp12MaxDiff=1,
            uniquenessRatio=10, speckleWindowSize=100, speckleRange=2,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)

        self.cap, dev = open_stereo(cv2, device, self.W, self.H)
        self.get_logger().info(f"camera opened on {dev}")

        self.pub_l = self.create_publisher(Image, "stereo/left/image_rect", 5)
        self.pub_r = self.create_publisher(Image, "stereo/right/image_rect", 5)
        self.pub_il = self.create_publisher(CameraInfo, "stereo/left/camera_info", 5)
        self.pub_ir = self.create_publisher(CameraInfo, "stereo/right/camera_info", 5)
        self.pub_d = self.create_publisher(Image, "stereo/depth_color", 5)
        self.pub_pc = self.create_publisher(PointCloud2, "stereo/points", 5)
        self.create_timer(0.001, self.tick)

    def make_info(self, P):
        m = CameraInfo()
        m.width, m.height = self.w, self.h
        m.distortion_model = "plumb_bob"
        m.d = [0.0] * 5
        m.k = P[:3, :3].flatten().tolist()
        m.r = np.eye(3).flatten().tolist()
        m.p = P.flatten().tolist()
        return m

    def image_msg(self, img, stamp):
        m = Image()
        m.header.stamp, m.header.frame_id = stamp, self.frame
        m.height, m.width = img.shape[:2]
        m.encoding = "bgr8"
        m.step = img.shape[1] * img.shape[2]
        m.data = img.tobytes()
        return m

    def tick(self):
        ok, frame = self.cap.read()
        if not ok:
            return
        now = time.monotonic()
        if now - self.last < self.min_dt:           # rate cap keeps CPU free for the rest of ROS
            return
        self.last = now
        stamp = self.get_clock().now().to_msg()

        size = (self.w, self.h)
        L = cv2.resize(frame[:, :self.W], size, interpolation=cv2.INTER_AREA)
        R = cv2.resize(frame[:, self.W:], size, interpolation=cv2.INTER_AREA)
        L = cv2.remap(L, *self.ml, cv2.INTER_LINEAR)
        R = cv2.remap(R, *self.mr, cv2.INTER_LINEAR)
        disp = self.sgbm.compute(cv2.cvtColor(L, cv2.COLOR_BGR2GRAY),
                                 cv2.cvtColor(R, cv2.COLOR_BGR2GRAY)).astype(np.float32) / 16.0

        for info in (self.info_l, self.info_r):
            info.header.stamp, info.header.frame_id = stamp, self.frame
        self.pub_l.publish(self.image_msg(L, stamp))
        self.pub_r.publish(self.image_msg(R, stamp))
        self.pub_il.publish(self.info_l)
        self.pub_ir.publish(self.info_r)

        vis = cv2.applyColorMap(
            cv2.convertScaleAbs(np.clip(disp, 0, self.nd), alpha=255.0 / self.nd), cv2.COLORMAP_JET)
        vis[disp <= 1.0] = 0
        self.pub_d.publish(self.image_msg(vis, stamp))

        # point cloud, computed directly: Z = f*B/d
        st = self.st
        d = disp[::st, ::st]
        ys, xs = np.nonzero(d > 1.0)
        if len(ys) == 0:
            return
        Z = self.f * self.B / d[ys, xs]
        keep = (Z > self.zmin) & (Z < self.zmax)
        ys, xs, Z = ys[keep] * st, xs[keep] * st, Z[keep]
        X = (xs - self.cx) * Z / self.f
        Y = (ys - self.cy) * Z / self.f
        bgr = L[ys, xs].astype(np.uint32)
        rgb = (bgr[:, 2] << 16) | (bgr[:, 1] << 8) | bgr[:, 0]

        cloud = np.empty(len(Z), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("rgb", "<u4")])
        cloud["x"], cloud["y"], cloud["z"], cloud["rgb"] = X, Y, Z, rgb

        pc = PointCloud2()
        pc.header.stamp, pc.header.frame_id = stamp, self.frame
        pc.height, pc.width = 1, len(Z)
        pc.fields = [PointField(name=n, offset=o, datatype=PointField.FLOAT32, count=1)
                     for n, o in (("x", 0), ("y", 4), ("z", 8), ("rgb", 12))]
        pc.is_bigendian, pc.is_dense = False, True
        pc.point_step, pc.row_step = 16, 16 * len(Z)
        pc.data = cloud.tobytes()
        self.pub_pc.publish(pc)


def main():
    rclpy.init()
    node = StereoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cap.release()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
