#!/usr/bin/env python3
# original By piddlerintheroot in CircuitsRaspberry Pi
import paho.mqtt.client as mqtt #mqtt kirjasto
import time
import sys
import argparse
import logging

from rpi_rf import RFDevice
broker="localhost" #brokerin osoite
port=1883 #portti

rpilahetin = mqtt.Client("luukku-rpi-433mhz") #mqtt objektin luominen
rpilahetin.username_pw_set("kayttaja","salari") #mqtt useri ja salarittanturi.connect("localhost", port=1883, keepalive=60) #Yhteys brokeriin (sama laite)
rpilahetin.connect(broker,port) #yhdista mqtt-brokeriin
luukkustatus = "kanala/ulko/luukku" #aihe jolla status julkaistaan


logging.basicConfig(level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S',
                    format='%(asctime)-15s - [%(levelname)s] %(module)s: %(message)s',)

parser = argparse.ArgumentParser(description='Sends a decimal code via a 433/315MHz GPIO device')
parser.add_argument('code', metavar='CODE', type=int,
                    help="Decimal code to send")
parser.add_argument('-g', dest='gpio', type=int, default=17,
                    help="GPIO pin (Default: 17)")
parser.add_argument('-p', dest='pulselength', type=int, default=None,
                    help="Pulselength (Default: 350)")
parser.add_argument('-t', dest='protocol', type=int, default=None,
                    help="Protocol (Default: 1)")
args = parser.parse_args()

rfdevice = RFDevice(args.gpio)
rfdevice.enable_tx()

if args.protocol:
    protocol = args.protocol
else:
    protocol = "default"
if args.pulselength:
    pulselength = args.pulselength
else:
    pulselength = "default"
logging.info(str(args.code) +
             " [protocol: " + str(protocol) +
             ", pulselength: " + str(pulselength) + "]")

rfdevice.tx_code(args.code, args.protocol, args.pulselength)
rfdevice.cleanup()

 Lahetetaan mqtt-brokerille tieto
if args.code == 3669736: #kiinni
 statustieto = 0 #tilabitti
elif args.code == 3669729: #auki
   statustieto = 1 #tilabitti
else:
 statustieto = 2 #virhebitti eli kaukosaatimen koodia ei tunnisteta

rpilahetin.publish(luukkustatus, payload=statustieto, retain=True)
rpilahetin.disconnect()
