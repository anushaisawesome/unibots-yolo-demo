"""
main_robot.py
=============
Integrates:
  - Localisation.py   (BallDetector - YOLO vision)
  - movement_v2.py    (Motor control)
  - behaviour.py      (State logic + PID steering)
  - state_machine.py  (State transitions)

Run this single file to operate the robot.
"""

import time
import math
import cv2
import numpy as np
import lgpio

import movement_v2

from Localisation import BallDetector


# =============================================================
# 1. CAMERA & MODEL SETUP
# =============================================================

# Replace with your actual calibrated camera matrix values
# Run cv2.calibrateCamera() with a checkerboard to get these
CAMERA_MATRIX = np.array([
    [800,   0, 320],
    [  0, 800, 240],
    [  0,   0,   1]
], dtype=float)

DIST_COEFFS = np.zeros(5)

MODEL_PATH = "runs/detect/ball_detector/weights/best.pt"  # Path to your trained model

detector = BallDetector(MODEL_PATH, CAMERA_MATRIX, DIST_COEFFS)
cap      = cv2.VideoCapture(0)   # 0 = first connected camera


# =============================================================
# 2. ENCODER SETUP (from behaviour.py — moved to its own class)
# =============================================================

class EncoderTracker:
    """
    Tracks wheel rotation counts using quadrature encoders.
    Used to estimate how far the robot has travelled for RETURN_HOME.
    """
    LEFT_A  = 17
    LEFT_B  = 18
    RIGHT_A = 27
    RIGHT_B = 22

    def __init__(self):
        self.left_count  = 0
        self.right_count = 0
        self.h = lgpio.gpiochip_open(0)

        for pin in [self.LEFT_A, self.LEFT_B, self.RIGHT_A, self.RIGHT_B]:
            lgpio.gpio_claim_input(self.h, pin)

        lgpio.callback(self.h, self.LEFT_A,  lgpio.RISING_EDGE, self._left_cb)
        lgpio.callback(self.h, self.RIGHT_A, lgpio.RISING_EDGE, self._right_cb)

    def _left_cb(self, chip, gpio, level, tick):
        b = lgpio.gpio_read(self.h, self.LEFT_B)
        self.left_count += 1 if b == 0 else -1

    def _right_cb(self, chip, gpio, level, tick):
        b = lgpio.gpio_read(self.h, self.RIGHT_B)
        self.right_count += 1 if b == 0 else -1

    def reset(self):
        self.left_count  = 0
        self.right_count = 0

    def average_ticks(self):
        return (self.left_count + self.right_count) / 2

    def close(self):
        lgpio.gpiochip_close(self.h)

encoder = EncoderTracker()


# =============================================================
# 3. ROBOT PARAMETERS (from behaviour.py)
# =============================================================

FRAME_CENTER         = 320   # Horizontal centre of camera frame in pixels
IMAGE_WIDTH          = 640   # Full frame width — used to know frame boundaries

BASE_SPEED           = 80    # Default forward drive speed (0-100)
SEARCH_SPEED         = 40    # Slower speed used when rotating to scan

Kp                   = 0.12  # Proportional gain for steering correction
                              # Higher = sharper turns, lower = smoother but slower to correct

COLLECTION_THRESHOLD = 20    # Distance in cm — robot stops and collects when closer than this
MAX_CAPACITY         = 5     # How many balls before robot returns home
RETURN_HOME_TIME_S   = 3     # Seconds to drive back — replace with encoder-based logic if needed


# =============================================================
# 4. SHARED ROBOT STATE
# =============================================================

ball_count   = 0    # How many balls collected this run
at_home      = False
dropped      = False


# =============================================================
# 5. VISION HELPER — wraps BallDetector into the format
#    behaviour.py originally expected: (detected, ball_x, distance)
# =============================================================

def detect_ball():
    """
    Grabs a fresh camera frame, runs YOLO detection,
    and returns the closest ball's info.

    Returns:
        ball_detected (bool)   — whether any ball is visible
        ball_x        (int)    — pixel x position of the closest ball's centre
        distance      (float)  — estimated distance in cm to the closest ball
    """
    ret, frame = cap.read()
    if not ret:
        return False, 0, 0

    detections = detector.detect(frame)

    if not detections:
        return False, 0, 0

    # Find the closest ball — position_3d[2] is depth/distance in metres
    closest = min(detections, key=lambda d: d["position_3d"][2])

    ball_x   = closest["center_px"][0]
    distance_cm = closest["position_3d"][2] * 100  # Convert metres → cm

    return True, ball_x, distance_cm


def detect_all_balls():
    """
    Returns full list of all current detections.
    Used in APPROACH to check if ball disappears mid-navigation.
    """
    ret, frame = cap.read()
    if not ret:
        return []
    return detector.detect(frame)


# =============================================================
# 6. BEHAVIOUR FUNCTIONS (from behaviour.py + state_machine.py)
# Each function runs one cycle of its state — called in the main loop
# =============================================================

def search_behavior():
    """
    SEARCH state: No ball visible.
    Slowly rotates in place until a ball comes into view.
    """
    print(" SEARCHING — rotating to scan")
    movement_v2.turn_left(SEARCH_SPEED)


def approach_behavior():
    """
    APPROACH state: Ball is visible.
    Uses proportional steering (PID-style) to centre the ball
    in the camera frame while driving forward.
    Stops and triggers collection when close enough.
    """
    ball_detected, ball_x, distance = detect_ball()

    if not ball_detected:
        # Ball disappeared mid-approach — go back to searching
        movement_v2.stop_drive()
        return

    # How far is the ball from the centre of the frame?
    # Positive error = ball is to the right, negative = to the left
    error           = ball_x - FRAME_CENTER
    turn_adjustment = Kp * error

    print(f"   APPROACH | ball_x={ball_x}px | dist={distance:.1f}cm | "
          f"error={error:+d} | adj={turn_adjustment:+.1f}")

    if turn_adjustment > 10:
        # Ball is noticeably to the right — turn right to re-centre
        movement_v2.turn_right(BASE_SPEED)

    elif turn_adjustment < -10:
        # Ball is noticeably to the left — turn left to re-centre
        movement_v2.turn_left(BASE_SPEED)

    else:
        # Ball is roughly centred — drive straight and run collector
        movement_v2.move_forward(BASE_SPEED)
        movement_v2.start_spinner()   # Spin the collector mechanism


def collect_behavior():
    """
    COLLECT state: Robot is very close to the ball.
    Stops driving, stops spinner, lifts the ball.
    """
    print(" COLLECTING ball")
    movement_v2.stop_drive()
    movement_v2.stop_spinner()

    # Lift mechanism picks up the ball
    movement_v2.lift_up(speed=80)
    time.sleep(1.0)   # Wait 1 second for lift to complete
    movement_v2.stop_lift()


def return_home_behavior():
    """
    RETURN HOME state: Capacity full.
    Drives back toward home using timed reverse.
    For better accuracy, replace time.sleep with encoder tick counting.
    """
    print(" RETURNING HOME")

    encoder.reset()    # Reset tick counter before measuring return journey

    movement_v2.move_backward(BASE_SPEED)

    # Drive back for a fixed time — crude but functional
    # TODO: replace with encoder distance tracking:
    #   while encoder.average_ticks() < TARGET_TICKS: pass
    time.sleep(RETURN_HOME_TIME_S)

    movement_v2.stop_drive()


def drop_behavior():
    """
    DROP state: At home, lower the lift to deposit collected balls.
    """
    print(" DROPPING balls at home")
    movement_v2.lift_down(speed=80)
    time.sleep(1.5)    # Wait for lift to lower
    movement_v2.stop_lift()


# =============================================================
# 7. STATE MACHINE MAIN LOOP (from state_machine.py)
# =============================================================

def run():
    global ball_count, at_home, dropped

    state = 'SEARCHING'

    print(" Robot starting up...")

    try:
        while True:

            # ---------------------------------------------------
            # RUN THE CURRENT STATE'S BEHAVIOUR
            # ---------------------------------------------------
            if state == 'SEARCHING':
                search_behavior()

            elif state == 'APPROACHING':
                approach_behavior()

            elif state == 'COLLECTING':
                collect_behavior()
                ball_count += 1
                print(f"  Collected! Total: {ball_count}/{MAX_CAPACITY}")

            elif state == 'RETURNING_HOME':
                return_home_behavior()
                at_home = True

            elif state == 'DROPPING':
                drop_behavior()
                ball_count = 0   # Reset count after dropping
                dropped    = True
                at_home    = False

            # ---------------------------------------------------
            # CHECK TRANSITION CONDITIONS (from state_machine.py)
            # These determine what the NEXT state will be
            # ---------------------------------------------------
            ball_detected, ball_x, distance = detect_ball()

            close_to_ball = ball_detected and distance < COLLECTION_THRESHOLD

            # State transition logic — evaluated top to bottom,
            # so more urgent conditions (like full capacity) take priority
            if state == 'SEARCHING' and ball_detected:
                print("  Ball spotted — switching to APPROACHING")
                state = 'APPROACHING'

            elif state == 'APPROACHING' and not ball_detected:
                print("  Ball lost — back to SEARCHING")
                state = 'SEARCHING'

            elif state == 'APPROACHING' and close_to_ball:
                print(" Close enough — switching to COLLECTING")
                state = 'COLLECTING'

            elif state == 'COLLECTING':
                if ball_count >= MAX_CAPACITY:
                    print(f" Capacity full ({ball_count}) — RETURNING HOME")
                    state = 'RETURNING_HOME'
                else:
                    # Go find another ball
                    state = 'SEARCHING'

            elif state == 'RETURNING_HOME' and at_home:
                state = 'DROPPING'

            elif state == 'DROPPING' and dropped:
                dropped = False
                state   = 'SEARCHING'

            # Small delay to avoid hammering the CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n Interrupted by user — shutting down")

    finally:
        # Always clean up hardware on exit
        movement_v2.shutdown()
        encoder.close()
        cap.release()
        cv2.destroyAllWindows()
        print("Shutdown complete")


# =============================================================
# 8. ENTRY POINT
# =============================================================

if __name__ == "__main__":
    run()