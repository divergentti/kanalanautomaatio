"""" This script controls inside curtain in the chicken house (or anything what 5V stepper motor can handle).

Operation basics: measures distance from two HCSR-04 sensors and if distance is > 30 cm, opens the curtain, else
closes the curtain.

Installation with ESP32 Dev Board: connect pins as in the parameters.py and for the echo-pin use either 
  voltage splitter or level converter from 5V to 3.3V.

Stepper motor: 28BYJ-48, control board ULN2003.

Sensors: HCSR-04 datasheet: https://datasheetspdf.com/pdf/1380136/ETC/HC-SR04/1
 Power Supply: +5V DC, Quiescent Current: <2mA, Working current: 15mA, Effectual Angle: <15º,
 Ranging Distance: 2-400 cm, Resolution: 0.3 cm, Measuring Angle: 30º, Trigger Input Pulse width: 10uS


Libraries:
 HCSR-04: https://github.com/rsc1975/micropython-hcsr04/blob/master/hcsr04.py
 MQTT_AS (not yet defined) https://github.com/peterhinch/micropython-mqtt/blob/master/mqtt_as/mqtt_as.py
 Stepper.py https://github.com/IDWizard/uln2003/blob/master/uln2003.py

14.12.2020 Jari Hiltunen
"""


import Steppermotor
from machine import Pin, ADC, reset
import uasyncio as asyncio
import utime
import gc
from MQTT_AS import MQTTClient, config
import network
from hcsr04 import HCSR04

try:
    f = open('parameters.py', "r")
    from parameters import SSID1, SSID2, PASSWORD1, PASSWORD2, MQTT_SERVER, MQTT_PASSWORD, MQTT_USER, MQTT_PORT, \
        CLIENT_ID, BATTERY_ADC_PIN, TOPIC_ERRORS, STEPPER1_PIN1, STEPPER1_PIN2, STEPPER1_PIN3, STEPPER1_PIN4, \
        STEPPER1_DELAY, HCSR04_1_ECHO_PIN, HCSR04_1_TRIGGER_PIN, HCSR04_2_TRIGGER_PIN, HCSR04_2_ECHO_PIN
except OSError:  # open failed
    print("parameter.py-file missing! Can not continue!")
    raise

#  Globals
previous_mqtt = utime.time()
use_wifi_password = None


""" Network setup"""
if network.WLAN(network.STA_IF).config('essid') == SSID1:
    use_wifi_password = PASSWORD1
elif network.WLAN(network.STA_IF).config('essid') == SSID2:
    use_wifi_password = PASSWORD2

config['server'] = MQTT_SERVER
config['ssid'] = network.WLAN(network.STA_IF).config('essid')
config['wifi_pw'] = use_wifi_password
config['user'] = MQTT_USER
config['password'] = MQTT_PASSWORD
config['port'] = MQTT_PORT
config['client_id'] = CLIENT_ID
client = MQTTClient(config)


def restart_and_reconnect():
    #  Last resort
    utime.sleep(5)
    reset()


class StepperMotor:
    """ ULN2003-based control, half steps. Asynchronous setup. """

    def __init__(self, in1, in2, in3, in4, indelay):
        self.motor = Steppermotor.create(Pin(in1, Pin.OUT), Pin(in2, Pin.OUT), Pin(in3, Pin.OUT),
                                         Pin(in4, Pin.OUT), delay=indelay)
        self.full_rotation = int(4075.7728395061727 / 8)  # http://www.jangeox.be/2013/10/stepper-motor-28byj-48_25.html
        self.uplimit = 0
        self.toplimit = 500
        self.curtain_steps = 300
        self.up_down_delay = 5
        self.curtain_up = False
        self.curtain_up_time = None
        self.curtain_down_time = None

    async def turn_x_degrees_right(self, degrees):
        self.motor.angle(degrees)

    async def turn_x_degrees_left(self, degrees):
        self.motor.angle(degrees, -1)

    async def turn_x_steps_right(self, steps):
        self.motor.step(steps)

    async def turn_x_steps_left(self, steps):
        self.motor.step(steps, -1)

    async def zero_to_potision(self):
        self.motor.reset()

    async def roll_curtain_up(self):
        self.motor.step(self.curtain_steps)
        self.curtain_up = True
        await asyncio.sleep(self.up_down_delay)
        self.curtain_up_time = utime.localtime()

    async def roll_curtain_down(self):
        self.motor.step(self.curtain_steps, -1)
        self.curtain_up = False
        await asyncio.sleep(self.up_down_delay)
        self.curtain_down_time = utime.localtime()


class DistanceSensor:

    def __init__(self, trigger, echo):
        self.sensor = HCSR04(trigger_pin=trigger, echo_pin=echo)
        self.distancecm = None
        self.distancemm = None

    async def measure_distance_cm(self):
        try:
            self.distancecm = self.sensor.distance_cm()
            if self.distancecm > 0:
                return self.distancecm
            else:
                self.distancecm = 0
                return self.distancecm
        except OSError as ex:
            print('ERROR getting distance:', ex)

    async def measure_distance_cm_loop(self):
        while True:
            try:
                self.distancecm = self.sensor.distance_cm()
                if self.distancecm > 0:
                    pass
                else:
                    self.distancecm = 0
            except OSError as ex:
                print('ERROR getting distance:', ex)
            await asyncio.sleep_ms(1)

    async def measure_distance_mm(self):
        try:
            self.distancemm = self.sensor.distance_mm()
            if self.distancemm > 0:
                return self.distancemm
            else:
                self.distancemm = 0
                return self.distancemm
        except OSError as ex:
            print('ERROR getting distance:', ex)

    async def measure_distance_mm_loop(self):
        while True:
            try:
                self.distancemm = self.sensor.distance_mm()
                if self.distancemm > 0:
                    pass
                else:
                    self.distancemm = 0
            except OSError as ex:
                print('ERROR getting distance:', ex)
            await asyncio.sleep_ms(1)


async def resolve_date():
    (year, month, mdate, hour, minute, second, wday, yday) = utime.localtime()
    date = "%s.%s.%s time %s:%s:%s" % (mdate, month, year, "{:02d}".format(hour), "{:02d}".format(minute), "{:02d}".
                                       format(second))
    return date


async def error_reporting(error):
    # error message: date + time;uptime;devicename;ip;error;free mem
    errormessage = str(resolve_date()) + ";" + str(utime.ticks_ms()) + ";" \
        + str(CLIENT_ID) + ";" + str(network.WLAN(network.STA_IF).ifconfig()) + ";" + str(error) +\
        ";" + str(gc.mem_free())
    await client.publish(TOPIC_ERRORS, str(errormessage), retain=False)


async def mqtt_report():
    global previous_mqtt
    n = 0
    while True:
        await asyncio.sleep(5)
        # print('mqtt-publish', n)
        await client.publish('result', '{}'.format(n), qos=1)
        n += 1
        """ if (kaasusensori.eCO2_keskiarvo > 0) and (kaasusensori.tVOC_keskiarvo > 0) and \
                (utime.time() - previous_mqtt) > 60:
            try:
                await client.publish(AIHE_CO2, str(kaasusensori.eCO2_keskiarvo), retain=False, qos=0) """


reel_motor = StepperMotor(STEPPER1_PIN1, STEPPER1_PIN2, STEPPER1_PIN3, STEPPER1_PIN4, STEPPER1_DELAY)
inside_distance = DistanceSensor(HCSR04_1_TRIGGER_PIN, HCSR04_1_ECHO_PIN)
outside_distance = DistanceSensor(HCSR04_2_TRIGGER_PIN, HCSR04_2_ECHO_PIN)


async def show_what_i_do():
    while True:
        print("Inside distance: %s" % inside_distance.distancecm)
        print("Outside distance: %s" % outside_distance.distancecm)
        await asyncio.sleep(0.5)


async def main():
    MQTTClient.DEBUG = False
    # await client.connect()
    asyncio.create_task(show_what_i_do())
    #  Initialize reading loops
    asyncio.create_task(inside_distance.measure_distance_cm_loop())
    asyncio.create_task(outside_distance.measure_distance_cm_loop())
    #  Drive curtain up
    #  await reel_motor.roll_curtain_up()

    while True:
        if inside_distance.distancecm is not None:
            if (inside_distance.distancecm < 30) and (reel_motor.curtain_up is False):
                await reel_motor.roll_curtain_up()
            elif (inside_distance.distancecm > 30) and (reel_motor.curtain_up is True):
                await reel_motor.roll_curtain_down()
        await asyncio.sleep(0.1)

asyncio.run(main())