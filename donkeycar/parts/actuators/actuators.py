"""
actuators.py
Classes to control the motors and servos. These classes 
are wrapped in a mixer class before being used in the drive loop.
"""

import time

from ... import utils

        
class PCA9685:
    ''' 
    PWM motor controler using PCA9685 boards. 
    This is used for most RC Cars
    '''
    def __init__(self, channel, frequency=60):
        import Adafruit_PCA9685
        # Initialise the PCA9685 using the default address (0x40).
        self.pwm = Adafruit_PCA9685.PCA9685()
        self.pwm.set_pwm_freq(frequency)
        self.channel = channel

    def set_pulse(self, pulse):
        self.pwm.set_pwm(self.channel, 0, pulse) 

    def run(self, pulse):
        self.set_pulse(pulse)
        
class PWMSteering:
    """
    Wrapper over a PWM motor cotnroller to convert angles to PWM pulses.
    """
    LEFT_ANGLE = -1 
    RIGHT_ANGLE = 1

    def __init__(self, controller=None,
                       left_pulse=290,
                       right_pulse=490):

        self.controller = controller
        self.left_pulse = left_pulse
        self.right_pulse = right_pulse


    def run(self, angle):
        #map absolute angle to angle that vehicle can implement.
        pulse = utils.map_range(angle, 
                                self.LEFT_ANGLE, self.RIGHT_ANGLE,
                                self.left_pulse, self.right_pulse)

        self.controller.set_pulse(pulse)

    def shutdown(self):
        self.run(0) #set steering straight



class PWMThrottle:
    """
    Wrapper over a PWM motor cotnroller to convert -1 to 1 throttle
    values to PWM pulses.
    """
    MIN_THROTTLE = -1
    MAX_THROTTLE =  1

    def __init__(self, controller=None,
                       max_pulse=300,
                       min_pulse=490,
                       zero_pulse=350):

        self.controller = controller
        self.max_pulse = max_pulse
        self.min_pulse = min_pulse
        self.zero_pulse = zero_pulse
        
        #send zero pulse to calibrate ESC
        self.controller.set_pulse(self.zero_pulse)
        time.sleep(1)


    def run(self, throttle):
        if throttle > 0:
            pulse = utils.map_range(throttle,
                                    0, self.MAX_THROTTLE, 
                                    self.zero_pulse, self.max_pulse)
        else:
            pulse = utils.map_range(throttle,
                                    self.MIN_THROTTLE, 0, 
                                    self.min_pulse, self.zero_pulse)

        self.controller.set_pulse(pulse)
        
    def shutdown(self):
        self.run(0) #stop vehicle



class Adafruit_DCMotor_Hat:
    ''' 
    Adafruit DC Motor Controller 
    Used for each motor on a differential drive car.
    '''
    def __init__(self, motor_num):
        from Adafruit_MotorHAT import Adafruit_MotorHAT, Adafruit_DCMotor
        import atexit
        
        self.FORWARD = Adafruit_MotorHAT.FORWARD
        self.BACKWARD = Adafruit_MotorHAT.BACKWARD
        self.mh = Adafruit_MotorHAT(addr=0x60) 
        
        self.motor = self.mh.getMotor(motor_num)
        self.motor_num = motor_num
        
        atexit.register(self.turn_off_motors)
        self.speed = 0
        self.throttle = 0
    
        
    def run(self, speed):
        '''
        Update the speed of the motor where 1 is full forward and
        -1 is full backwards.
        '''
        if speed > 1 or speed < -1:
            raise ValueError( "Speed must be between 1(forward) and -1(reverse)")
        
        self.speed = speed
        self.throttle = int(utils.map_range(abs(speed), -1, 1, -255, 255))
        
        if speed > 0:            
            self.motor.run(self.FORWARD)
        else:
            self.motor.run(self.BACKWARD)
            
        self.motor.setSpeed(self.throttle)
        

    def shutdown(self):
        self.mh.getMotor(self.motor_num).run(Adafruit_MotorHAT.RELEASE)

class Maestro:
    '''
    Pololu Maestro Servo controller
    Use the MaestroControlCenter to set the speed & acceleration values to 0!
    '''
    import threading

    maestro_device = None
    astar_device = None
    maestro_lock = threading.Lock()
    astar_lock = threading.Lock()

    def __init__(self, channel, frequency = 60):
        import serial

        if Maestro.maestro_device == None:
            Maestro.maestro_device = serial.Serial('/dev/ttyACM0', 115200)

        self.channel = channel
        self.frequency = frequency
        self.lturn = False
        self.rturn = False
        self.headlights = False
        self.brakelights = False

        if Maestro.astar_device == None:
            Maestro.astar_device = serial.Serial('/dev/ttyACM2', 115200, timeout= 0.01)

    def set_pulse(self, pulse):
        # Recalculate pulse width from the Adafruit values
        w = pulse * (1 / (self.frequency * 4096)) # in seconds
        w *= 1000 * 1000  # in microseconds
        w *= 4  # in quarter microsenconds the maestro wants
        w = int(w)

        with Maestro.maestro_lock:
            Maestro.maestro_device.write(bytearray([ 0x84,
                                                     self.channel,
                                                     (w & 0x7F),
                                                     ((w >> 7) & 0x7F)]))

    def set_turn_left(self, v):
        if self.lturn != v:
            self.lturn = v
            b = bytearray('L' if v else 'l', 'ascii')
            with Maestro.astar_lock:
                Maestro.astar_device.write(b)

    def set_turn_right(self, v):
        if self.rturn != v:
            self.rturn = v
            b = bytearray('R' if v else 'r', 'ascii')
            with Maestro.astar_lock:
                Maestro.astar_device.write(b)

    def set_headlight(self, v):
        if self.headlights != v:
            self.headlights = v
            b = bytearray('H' if v else 'h', 'ascii')
            with Maestro.astar_lock:
                Maestro.astar_device.write(b)

    def set_brake(self, v):
        if self.brakelights != v:
            self.brakelights = v
            b = bytearray('B' if v else 'b', 'ascii')
            with Maestro.astar_lock:
                Maestro.astar_device.write(b)

    def readline(self):
        ret = None
        with Maestro.astar_lock:
            # expecting lines like
            # E n nnn n
            if Maestro.astar_device.inWaiting() > 8:
                ret = Maestro.astar_device.readline()

        if ret != None:
            ret = ret.rstrip()

        return ret

class Teensy:
    '''
    Teensy Servo controller
    '''
    import threading

    teensy_device = None
    astar_device = None
    teensy_lock = threading.Lock()
    astar_lock = threading.Lock()

    def __init__(self, channel, frequency = 60):
        import serial

        if Teensy.teensy_device == None:
            Teensy.teensy_device = serial.Serial('/dev/teensy', 115200, timeout = 0.01)

        self.channel = channel
        self.frequency = frequency
        self.lturn = False
        self.rturn = False
        self.headlights = False
        self.brakelights = False

        if Teensy.astar_device == None:
            Teensy.astar_device = serial.Serial('/dev/astar', 115200, timeout = 0.01)

    def set_pulse(self, pulse):
        # Recalculate pulse width from the Adafruit values
        w = pulse * (1 / (self.frequency * 4096)) # in seconds
        w *= 1000 * 1000  # in microseconds

        with Teensy.teensy_lock:
            Teensy.teensy_device.write(("%c %.1f\n" % (self.channel, w)).encode('ascii'))

    def set_turn_left(self, v):
        if self.lturn != v:
            self.lturn = v
            b = bytearray('L' if v else 'l', 'ascii')
            with Teensy.astar_lock:
                Teensy.astar_device.write(b)

    def set_turn_right(self, v):
        if self.rturn != v:
            self.rturn = v
            b = bytearray('R' if v else 'r', 'ascii')
            with Teensy.astar_lock:
                Teensy.astar_device.write(b)

    def set_headlight(self, v):
        if self.headlights != v:
            self.headlights = v
            b = bytearray('H' if v else 'h', 'ascii')
            with Teensy.astar_lock:
                Teensy.astar_device.write(b)

    def set_brake(self, v):
        if self.brakelights != v:
            self.brakelights = v
            b = bytearray('B' if v else 'b', 'ascii')
            with Teensy.astar_lock:
                Teensy.astar_device.write(b)

    def teensy_readline(self):
        ret = None
        with Teensy.teensy_lock:
            # expecting lines like
            # E n nnn n
            if Teensy.teensy_device.inWaiting() > 8:
                ret = Teensy.teensy_device.readline()

        if ret != None:
            ret = ret.rstrip()

        return ret

    def astar_readline(self):
        ret = None
        with Teensy.astar_lock:
            # expecting lines like
            # E n nnn n
            if Teensy.astar_device.inWaiting() > 8:
                ret = Teensy.astar_device.readline()

        if ret != None:
            ret = ret.rstrip()

        return ret

class HBridge_DC_Motor(object):
    '''
    Motor controlled with an hbridge from the gpio pins on Rpi
    '''
    def __init__(self, pin_forward, pin_backward, pwm_pin):
        import RPi.GPIO as GPIO
        self.pin_forward = pin_forward
        self.pin_backward = pin_backward
        self.pwm_pin = pwm_pin

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin_forward, GPIO.OUT)
        GPIO.setup(self.pin_backward, GPIO.OUT)
        GPIO.setup(self.pwm_pin, GPIO.OUT)

        freq = 50 #HZ
        self.pwm = GPIO.PWM(self.pwm_pin, freq)
        self.pwm.start(0)

    def run(self, speed):
        import RPi.GPIO as GPIO
        '''
        Update the speed of the motor where 1 is full forward and
        -1 is full backwards.
        '''
        if speed > 1 or speed < -1:
            raise ValueError( "Speed must be between 1(forward) and -1(reverse)")
        
        self.speed = speed
        max_duty = 90 #I've read 90 is a good max
        self.throttle = int(utils.map_range(speed, -1, 1, -max_duty, max_duty))
        
        if self.throttle > 0:
            self.pwm.ChangeDutyCycle(self.throttle)
            GPIO.output(self.pin_forward, GPIO.HIGH)
            GPIO.output(self.pin_backward, GPIO.LOW)
        elif self.throttle < 0:
            self.pwm.ChangeDutyCycle(-self.throttle)
            GPIO.output(self.pin_forward, GPIO.LOW)
            GPIO.output(self.pin_backward, GPIO.HIGH)
        else:
            self.pwm.ChangeDutyCycle(self.throttle)
            GPIO.output(self.pin_forward, GPIO.LOW)
            GPIO.output(self.pin_backward, GPIO.LOW)


    def shutdown(self):
        import RPi.GPIO as GPIO
        self.pwm.stop()
        GPIO.cleanup()


class TwoWheelSteeringThrottle(object):

    def run(self, throttle, steering):
        if throttle > 1 or throttle < -1:
            raise ValueError( "throttle must be between 1(forward) and -1(reverse)")
 
        if steering > 1 or steering < -1:
            raise ValueError( "steering must be between 1(right) and -1(left)")

        left_motor_speed = throttle
        right_motor_speed = throttle
 
        if steering < 0:
            left_motor_speed *= (1.0 - (-steering))
        elif steering > 0:
            right_motor_speed *= (1.0 - steering)

        return left_motor_speed, right_motor_speed

    def shutdown(self):
        pass


class MockActuator(object):
    def __init__(self):
        pass

    def run(self, pulse):
        pass

    def shutdown(self):
        pass