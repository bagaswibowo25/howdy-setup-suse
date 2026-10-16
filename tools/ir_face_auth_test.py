#!/usr/bin/env python3
# Set the Microsoft XU FACE_AUTHENTICATION mode, then stream and print the mean
# brightness of each frame. Alternating bright/dark frames = IR emitter flashing.
#
# Usage: python3 ir_face_auth_test.py [device] [mode] [unit]
#   mode 1 = non-authentication (emitter off), 2 = alternating IR (Windows Hello)
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uvcxu import length, query

device = sys.argv[1] if len(sys.argv) > 1 else "/dev/video2"
mode = int(sys.argv[2]) if len(sys.argv) > 2 else 2
unit = int(sys.argv[3]) if len(sys.argv) > 3 else 7
selector = 6

fd = os.open(device, os.O_RDWR)
size = length(fd, unit, selector)
value = query(fd, unit, selector, 0x81, size)
value[2] = mode
query(fd, unit, selector, 0x01, size, value)
print("FACE_AUTHENTICATION now:", query(fd, unit, selector, 0x81, size))
os.close(fd)

cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
means = []
for _ in range(40):
	ok, frame = cap.read()
	means.append(round(float(frame.mean()), 1) if ok else None)
cap.release()
print("frame means:", means)
