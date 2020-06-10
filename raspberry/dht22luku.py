# !/usr/bin/python3
# jos CRON:ssa, ps -A ja kill prosessi ensin!
# 10.6.2020 Jari Hiltunen
import paho.mqtt.client as mqtt # tuodaan mqtt kirjasto
# asennus pip3 install paho-mqtt
import time
import Adafruit_DHT # vanha toimiva adafruit-kirjasto
# muuttujat tuodaan parametrit.py_tiedostosta
from parametrit import ANTURINIMI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERI, MQTTSERVERIPORTTI, \
    AIHELAMPO, AIHEKOSTEUS, DHT22PINNI, LUKUVALI

mqttanturi = mqtt.Client(ANTURINIMI)   # mqtt objektin luominen
mqttanturi.username_pw_set(MQTTKAYTTAJA, MQTTSALARI) # mqtt useri ja salari
mqttanturi.connect(MQTTSERVERI, port=MQTTSERVERIPORTTI, keepalive=60) # Yhteys brokeriin
mqttanturi.loop_start() # Loopin kaynnistys
# dhtLaite = adafruit_dht.DHT22(DHT22PINNI) # tarpeeton DHT-anturiobjekti

while True:
    try:
       
        kosteus, lampo = Adafruit_DHT.read_retry(22, DHT22PINNI)
        if lampo is not None:
            lampo ='{:.1f}'.format(lampo)
            print("Lampo: %s" % str(lampo))
            mqttanturi.publish(AIHELAMPO, payload=lampo, retain=True)
        else:
         print (time.strftime("%H:%M:%S ") + "Lampotilatietoa ei saatavilla")
        if kosteus is not None:
           kosteus = '{:.1f}'.format(kosteus)
           print("Kosteus: %s" % str(kosteus))
           mqttanturi.publish(AIHEKOSTEUS, payload=kosteus, retain=True)
        else:
            print(time.strftime("%H:%M:%S ") + "Kosteustietoa ei saatavilla")
        time.sleep(LUKUVALI) # lukufrekvenssi
    except RuntimeError as error:
        print(error.args[0])
