#!/usr/bin/env python3
# ohjaa mqtt-viesteilla tassa tapauksessa reletta, joka ohjaa kanalan puhallinta
# Jari Hiltunen 14.6.2020
# parametrina releen ohjaustieto, joka voi olla:
# 0 = molemmat releet pois
# 1 = rele 1 on, rele 2 off
# 2 = molemmat on
# 3 = rele 1 off, rele 2 on

import paho.mqtt.client as mqtt #mqtt kirjasto
import time
import sys
# suoritetaan Raspberrylla
broker="localhost" # brokerin osoite
port=1883 # portti
rpilahetin = mqtt.Client("puhaltimen-ohjaus") # mqtt objektin luominen
rpilahetin.username_pw_set("kanainmqtt","123kana321") # mqtt useri ja salari
rpilahetin.connect(broker,port) # yhdista mqtt-brokeriin
luukkustatus = "kanala/sisa/puhallin" # aihe jolla status julkaistaan
viesti = sys.argv[1] # argumentti 1

# Lahetetaan mqtt-brokerille tieto
if (int(viesti) >= 0) and (int(viesti) < 4):
    statustieto = viesti
    try:
        rpilahetin.publish(luukkustatus, payload=statustieto, retain=True)
        print("Releen ohjaus %s lahetetty" % statustieto)
    except:
        print("Ongelma lahetyksessa!")
        rpilahetin.disconnect()
else:
    print("Arvo valilta 0 -3 kiitos!")
