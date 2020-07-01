#!/usr/bin/env python3
# Relemoduleiden ohjaus
# NC = Normally Connected
# NO = Normally Open
# 1.7.2020 Jari Hiltunen

import paho.mqtt.client as mqtt # mqtt kirjasto
import RPi.GPIO as GPIO
import time
rele1_pinni = 26
rele2_pinni = 19
rele3_pinni = 13
rele4_pinni = 6
GPIO.setmode(GPIO.BCM)
# Releiden pinnit
GPIO.setup(rele1_pinni, GPIO.OUT)
GPIO.setup(rele2_pinni, GPIO.OUT)
GPIO.setup(rele3_pinni, GPIO.OUT)
GPIO.setup(rele4_pinni, GPIO.OUT)
# Releiden logiikat
# 0 = NC = Normally Closed
# 1 = NO = Normally Open
# Tilastatusta varten
aiempi_rele1_viesti = None  # aiempi tilaviesti
aiempi_rele2_viesti = None  # aiempi tilaviesti
aiempi_rele3_viesti = None  # aiempi tilaviesti
aiempi_rele4_viesti = None  # aiempi tilaviesti
# Aihe1 = rele1 jne.

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    # print("Yhdistetty " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aiheet
    mqttasiakas.subscribe(MQTTAIHE_1)  # tilaa aihe releelle 1
    mqttasiakas.subscribe(MQTTAIHE_2)  # tilaa aihe releelle 2
    mqttasiakas.subscribe(MQTTAIHE_3)  # tilaa aihe releelle 3
    mqttasiakas.subscribe(MQTTAIHE_4)  # tilaa aihe releelle 4


def mqttviesti(mqttasiakas, userdata, message):
    global aiempi_rele1_viesti, aiempi_rele2_viesti, \
        aiempi_rele3_viesti, aiempi_rele4_viesti # ei toteuteta jos ei muutosta
    # Looppia voi lyhentaa laskurin avulla esim. MQTTAIHE_x jossa x on laskuri
    # jos releiden logiikka on sama.
    viesti = int(message.payload)
    if (viesti < 0) or (viesti > 1):
        print("Virheellinen arvo!")
        return False
    # releelle ja aiheelle 1
    if (message.topic == MQTTAIHE_1) and (viesti == 0) and (viesti != aiempi_rele1_viesti):
        try:
            GPIO.output(rele1_pinni, 0)
            aiempi_rele1_viesti = 0
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    if (message.topic == MQTTAIHE_1) and (viesti == 1) and (viesti != aiempi_rele1_viesti):
        try:
            GPIO.output(rele1_pinni, 1)
            aiempi_rele1_viesti = 1
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    # releelle ja aiheelle 2
    if (message.topic == MQTTAIHE_2) and (viesti == 0) and (viesti != aiempi_rele2_viesti):
        try:
            GPIO.output(rele2_pinni, 0)
            aiempi_rele2_viesti = 0
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    if (message.topic == MQTTAIHE_2) and (viesti == 1) and (viesti != aiempi_rele2_viesti):
        try:
            GPIO.output(rele2_pinni, 1)
            aiempi_rele2_viesti = 1
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    # releelle ja aiheelle 3
    if (message.topic == MQTTAIHE_3) and (viesti == 0) and (viesti != aiempi_rele3_viesti):
        try:
            GPIO.output(rele3_pinni, 0)
            aiempi_rele3_viesti = 0
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    if (message.topic == MQTTAIHE_3) and (viesti == 1) and (viesti != aiempi_rele3_viesti):
        try:
            GPIO.output(rele3_pinni, 1)
            aiempi_rele3_viesti = 1
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    # releelle ja aiheelle 4
    if (message.topic == MQTTAIHE_4) and (viesti == 0) and (viesti != aiempi_rele4_viesti):
        try:
            GPIO.output(rele4_pinni, 0)
            aiempi_rele4_viesti = 0
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    if (message.topic == MQTTAIHE_4) and (viesti == 1) and (viesti != aiempi_rele4_viesti):
        try:
            GPIO.output(rele4_pinni, 1)
            aiempi_rele4_viesti = 1
            time.sleep(1)
        except OSError:
            print("Virhe %d" %OSError)
            GPIO.cleanup()
            return False
    return  # mqttviesti

broker = "localhost" #brokerin osoite
port = 1883 #portti
# reileille tilattavat mtqq-aiheet
MQTTAIHE_1 = 'kanala/sisa/valaistus' # aihe josta valon status luetaan
MQTTAIHE_2 = 'kanala/sisa/lammitys' # aihe josta lammityksen status luetaan
MQTTAIHE_3 = 'kanala/ulko/valaistus' # aihe josta ulkovalon status luetaan
MQTTAIHE_4 = 'kanala/ulko/halytys' # aihe josta halytys status luetaan

# mqtt-objektin luominen
mqttasiakas = mqtt.Client("2x2rele-broker") # mqtt objektin luominen
mqttasiakas.on_connect = mqttyhdista # mita tehdaan kun yhdistetaan brokeriin
mqttasiakas.on_message = mqttviesti # maarita mita tehdaan kun viesti saapuu
mqttasiakas.username_pw_set("useri","salari") # mqtt useri ja salari
mqttasiakas.connect(broker, port, keepalive=60, bind_address="") # yhdista mqtt-brokeriin

try:
    while True:
        mqttasiakas.loop_start()
        time.sleep(1)

except KeyboardInterrupt:
    GPIO.cleanup()
    pass
