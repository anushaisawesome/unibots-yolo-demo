import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ==========================
# Lift Motor (Driver 2)
# ==========================

LIFT_IN1 = 20
LIFT_IN2 = 21
LIFT_ENA = 16

GPIO.setup(LIFT_IN1, GPIO.OUT)
GPIO.setup(LIFT_IN2, GPIO.OUT)
GPIO.setup(LIFT_ENA, GPIO.OUT)

lift_pwm = GPIO.PWM(LIFT_ENA, 1000)
lift_pwm.start(0)

# ==========================
# Lift Functions
# ==========================

def lift_up(speed=80):
    lift_pwm.ChangeDutyCycle(speed)
    GPIO.output(LIFT_IN1, GPIO.HIGH)
    GPIO.output(LIFT_IN2, GPIO.LOW)

def lift_down(speed=80):
    lift_pwm.ChangeDutyCycle(speed)
    GPIO.output(LIFT_IN1, GPIO.LOW)
    GPIO.output(LIFT_IN2, GPIO.HIGH)

def stop_lift():
    lift_pwm.ChangeDutyCycle(0)
    GPIO.output(LIFT_IN1, GPIO.LOW)
    GPIO.output(LIFT_IN2, GPIO.LOW)

try:
    print("Lift up")
    lift_up()
    time.sleep(3)

    print("Stop lift")
    stop_lift()
    time.sleep(2)

    print("Lift down")
    lift_down()
    time.sleep(3)

    stop_lift()

finally:
    GPIO.cleanup()

'''
Lift Motor (Driver 2)
L298N Pin	Raspberry Pi
IN3	        GPIO20
IN4	        GPIO21
ENB	        GPIO16 (PWM)'''