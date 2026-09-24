"""Webcam-based privacy blur prototype (macOS).
Blurs all screens unless the enrolled owner faces the camera (yaw < YAW_LIMIT).
Enroll once: python3 blur_mac.py --enroll. Quit: menu bar item -> Quit, or Ctrl+C.
"""
import os
import sys
import threading
import time

import cv2
import numpy as np
from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory, NSBackingStoreBuffered,
                    NSColor, NSMenu, NSMenuItem, NSScreen, NSStatusBar, NSVariableStatusItemLength,
                    NSVisualEffectView, NSWindow)
from PyObjCTools import AppHelper

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "..", "models")
MODEL = os.path.join(MODELS, "face_detection_yunet_2023mar.onnx")
REC_MODEL = os.path.join(MODELS, "face_recognition_sface_2021dec.onnx")
OWNER_FILE = os.path.join(HERE, "owner.npy")
MATCH_THRESHOLD = 0.363  # SFace cosine threshold (opencv_zoo)
ENROLL_SAMPLES = 10
YAW_LIMIT = 60       # degrees of head turn before blurring
NOSE_DEPTH = 0.55    # nose protrusion / eye distance, calibrates yaw estimate
DEBUG = False        # print estimated yaw per frame
AWAY_FRAMES = 5      # consecutive misses before blurring
BACK_FRAMES = 2      # consecutive hits before unblurring

WINDOW_LEVEL = 1000                  # NSScreenSaverWindowLevel
BORDERLESS = 0                       # NSWindowStyleMaskBorderless
ALL_SPACES_STATIONARY = 1 | 16 | 256  # canJoinAllSpaces | stationary | fullScreenAuxiliary
MATERIAL_FULLSCREEN_UI = 15
BLEND_BEHIND_WINDOW = 0
STATE_ACTIVE = 1


class Tracker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.facing = True
        for _ in range(15):  # camera may not be ready right after login
            self.cam = cv2.VideoCapture(0)
            if self.cam.isOpened():
                break
            time.sleep(2)
        else:
            raise SystemExit("Webcam not available (check System Settings > Privacy > Camera)")
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
        while True:
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


class Overlay:
    """One click-through native blur window per screen (NSVisualEffectView blurs live content)."""

    def __init__(self, tracker):
        self.tracker = tracker
        self.blurred = False
        self.windows = []
        for screen in NSScreen.screens():
            frame = screen.frame()
            w = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame, BORDERLESS, NSBackingStoreBuffered, False)
            w.setLevel_(WINDOW_LEVEL)
            w.setOpaque_(False)
            w.setBackgroundColor_(NSColor.clearColor())
            w.setIgnoresMouseEvents_(True)
            w.setCollectionBehavior_(ALL_SPACES_STATIONARY)
            w.setReleasedWhenClosed_(False)
            v = NSVisualEffectView.alloc().initWithFrame_(((0, 0), frame.size))
            v.setMaterial_(MATERIAL_FULLSCREEN_UI)
            v.setBlendingMode_(BLEND_BEHIND_WINDOW)
            v.setState_(STATE_ACTIVE)
            w.setContentView_(v)
            w.setAlphaValue_(0.0)
            w.orderFrontRegardless()
            self.windows.append(w)
        self.tick()

    def tick(self):
        want = not self.tracker.facing
        if want != self.blurred:
            self.blurred = want
            for w in self.windows:
                w.setAlphaValue_(1.0 if want else 0.0)
                w.orderFrontRegardless()
        AppHelper.callLater(0.05, self.tick)


def status_item():
    item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    item.button().setTitle_("Blur")
    menu = NSMenu.alloc().init()
    menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "q"))
    item.setMenu_(menu)
    return item


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
    t = Tracker()
    if "--enroll" in sys.argv:
        enroll(t)
        raise SystemExit
    if t.owner is None:
        raise SystemExit("No enrolled face. Run: python3 blur_mac.py --enroll")
    t.start()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    item = status_item()
    overlay = Overlay(t)
    print("Running. Look away to blur. Quit: menu bar 'Blur' -> Quit, or Ctrl+C")
    AppHelper.runEventLoop(installInterrupt=True)
