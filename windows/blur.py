"""Webcam-based privacy blur prototype.
Blurs the primary screen unless the enrolled owner faces it (yaw < YAW_LIMIT).
Enroll once: python blur.py --enroll. Quit: Ctrl+Shift+Q.
"""
import ctypes
import os
import threading
import time

import cv2
import mss
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "..", "models")
MODEL = os.path.join(MODELS, "face_detection_yunet_2023mar.onnx")
REC_MODEL = os.path.join(MODELS, "face_recognition_sface_2021dec.onnx")
OWNER_FILE = os.path.join(HERE, "owner.npy")
MATCH_THRESHOLD = 0.363  # SFace cosine threshold (opencv_zoo)
ENROLL_SAMPLES = 10
YAW_LIMIT = 60      # degrees of head turn before blurring
NOSE_DEPTH = 0.55    # nose protrusion / eye distance, calibrates yaw estimate
DEBUG = False        # print estimated yaw per frame
AWAY_FRAMES = 5     # consecutive misses before blurring
BACK_FRAMES = 2      # consecutive hits before unblurring
DOWNSCALE = 12       # blur works on a downscaled capture
REFRESH_MS = 100     # blurred frame refresh while blurred

GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x8000000
WDA_EXCLUDEFROMCAPTURE = 0x11
VK_CONTROL, VK_SHIFT, VK_Q = 0x11, 0x10, 0x51


class Tracker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.facing = True
        self.running = True
        while True:  # camera may be busy right after logon (e.g. Windows Hello)
            self.cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if self.cam.isOpened() and self.cam.read()[0]:
                break
            self.cam.release()
            print(time.strftime("%X"), "webcam not ready, retrying")
            time.sleep(5)
        self.det = cv2.FaceDetectorYN.create(MODEL, "", (320, 240), 0.6)
        self.rec = cv2.FaceRecognizerSF.create(REC_MODEL, "")
        self.owner = np.load(OWNER_FILE) if os.path.exists(OWNER_FILE) else None

    def detect(self, frame):
        """Largest face in full-frame coordinates, or None."""
        _, faces = self.det.detect(cv2.resize(frame, (320, 240)))
        if faces is None:
            return None
        f = max(faces, key=lambda r: r[2] * r[3]).copy()
        f[0:14:2] *= frame.shape[1] / 320
        f[1:14:2] *= frame.shape[0] / 240
        return f

    def feature(self, frame, f):
        return self.rec.feature(self.rec.alignCrop(frame, f))

    def is_owner(self, frame, f):
        feat = self.feature(frame, f)
        return max(self.rec.match(feat, o[None], cv2.FaceRecognizerSF_FR_COSINE)
                   for o in self.owner) >= MATCH_THRESHOLD

    @staticmethod
    def yaw(f):
        """Estimated head yaw in degrees."""
        rx, lx, nx = f[4], f[6], f[8]  # right eye, left eye, nose tip x
        eye_dist = abs(lx - rx)
        if eye_dist < 1:
            return 90.0
        r = (nx - (rx + lx) / 2) / eye_dist
        return float(np.degrees(np.arctan(abs(r) / NOSE_DEPTH)))

    def run(self):
        hits = misses = 0
        while self.running:
            ok, frame = self.cam.read()
            if not ok:
                time.sleep(0.05)
                continue
            f = self.detect(frame)
            y = None if f is None else self.yaw(f)
            found = y is not None and y < YAW_LIMIT and self.is_owner(frame, f)
            if DEBUG:
                print("yaw:", "-" if y is None else round(y), "owner:", found)
            hits, misses = (hits + 1, 0) if found else (0, misses + 1)
            if misses >= AWAY_FRAMES:
                self.facing = False
            elif hits >= BACK_FRAMES:
                self.facing = True
        self.cam.release()


class Overlay:
    def __init__(self, tracker):
        self.tracker = tracker
        self.sct = mss.MSS()
        self.mon = self.sct.monitors[1]
        self.w, self.h = self.mon["width"], self.mon["height"]

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.w}x{self.h}+{self.mon['left']}+{self.mon['top']}")
        self.root.attributes("-topmost", True, "-alpha", 0.0)
        self.label = tk.Label(self.root, bd=0)
        self.label.pack(fill="both", expand=True)
        self.root.update()

        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

        self.blurred = False
        self.tick()

    def render(self):
        shot = np.asarray(self.sct.grab(self.mon))[:, :, 2::-1]  # BGRA -> RGB
        small = cv2.resize(shot, (self.w // DOWNSCALE, self.h // DOWNSCALE), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), 3)
        img = Image.fromarray(small).resize((self.w, self.h), Image.BILINEAR)
        self.photo = ImageTk.PhotoImage(img)
        self.label.configure(image=self.photo)

    def tick(self):
        if all(user32.GetAsyncKeyState(k) & 0x8000 for k in (VK_CONTROL, VK_SHIFT, VK_Q)):
            print(time.strftime("%c"), "quit by hotkey")
            self.tracker.running = False
            self.root.destroy()
            return
        want = not self.tracker.facing
        if want:
            self.render()
        if want != self.blurred:
            self.blurred = want
            self.root.attributes("-alpha", 1.0 if want else 0.0)
            self.root.attributes("-topmost", True)
        self.root.after(REFRESH_MS if want else 50, self.tick)


def enroll(t):
    print(f"Enrolling: look straight at the camera ({ENROLL_SAMPLES} samples)...")
    feats = []
    while len(feats) < ENROLL_SAMPLES:
        ok, frame = t.cam.read()
        f = t.detect(frame) if ok else None
        if f is not None and t.yaw(f) < 20:
            feats.append(t.feature(frame, f)[0])
            print(f"  {len(feats)}/{ENROLL_SAMPLES}")
            time.sleep(0.3)
    np.save(OWNER_FILE, np.array(feats))
    t.cam.release()
    print("Saved", OWNER_FILE)


if __name__ == "__main__":
    import sys
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\AutoBlurOnYourLaptop")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS: already running
        raise SystemExit
    if sys.stderr is None:  # pythonw: no console, log to file
        sys.stdout = sys.stderr = open(os.path.join(HERE, "blur.log"), "a", buffering=1)
        import faulthandler
        faulthandler.enable(sys.stderr)  # log native crashes too
        print(time.strftime("%c"), "started")
    t = Tracker()
    if "--enroll" in sys.argv:
        enroll(t)
        raise SystemExit
    if t.owner is None:
        raise SystemExit("No enrolled face. Run: python blur.py --enroll")
    t.start()
    print("Running. Look away to blur. Quit: Ctrl+Shift+Q")
    Overlay(t).root.mainloop()
