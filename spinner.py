import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ==========================
# Spinner Motor (Driver 1)
# ==========================

SPIN_IN1 = 5
SPIN_IN2 = 6
SPIN_ENA = 13   # PWM speed control

GPIO.setup(SPIN_IN1, GPIO.OUT)
GPIO.setup(SPIN_IN2, GPIO.OUT)
GPIO.setup(SPIN_ENA, GPIO.OUT)

spinner_pwm = GPIO.PWM(SPIN_ENA, 1000)
spinner_pwm.start(0)

# ==========================
# Spinner Functions
# ==========================

def start_spinner(speed=100):
    spinner_pwm.ChangeDutyCycle(speed)
    GPIO.output(SPIN_IN1, GPIO.HIGH)
    GPIO.output(SPIN_IN2, GPIO.LOW)

def stop_spinner():
    spinner_pwm.ChangeDutyCycle(0)
    GPIO.output(SPIN_IN1, GPIO.LOW)
    GPIO.output(SPIN_IN2, GPIO.LOW)

try:
    print("Starting spinner")
    start_spinner(100)
    time.sleep(5)

    print("Stopping spinner")
    stop_spinner()
    time.sleep(2)

finally:
    GPIO.cleanup()

'''
Spinner Motor (Driver 1)
L298N Pin	Raspberry Pi
IN1	        GPIO5
IN2	        GPIO6
ENA	        GPIO13 (PWM)


'''