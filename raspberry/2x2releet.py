#!/usr/bin/env python3
"""
Relemoduleiden ohjaus scripti. Scripti lukee relepinnien mukaisia GPIO-portteja
ja sen mukaisesti ohjaa releen paalle tai pois. Huomioi releiden kytkennat, eli:
 NC = Normally Connected
 NO = Normally Open
jolloin arvo 1 voi olla siis joko rele auki tai kiinni kytkennasta riippuen.

Ohjelmakoodissa arvo 0 tarkoittaa sita, etta releelle tuodaan jannite.

5.7.2020 Jari Hiltunen
4.11.2020: Lisätty virheloggeri

"""

import paho.mqtt.client as mqtt  # mqtt kirjasto
import RPi.GPIO as GPIO
import time
import os
import logging
from dateutil import tz
import datetime
import signal
import sys
from parametrit import RELE1_PINNI, RELE2_PINNI, RELE3_PINNI, RELE4_PINNI, \
    RELE1_MQTTAIHE_1, RELE2_MQTTAIHE_2, RELE3_MQTTAIHE_3, RELE4_MQTTAIHE_4, \
    MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI


''' Globaalit päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/2x2releohjaus-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/2x2releohjaus-virhe.log'):
    logi = logging.getLogger(login_nimi)
    login_formaatti = logging.Formatter(login_formaatti)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(login_formaatti)
    logi.addHandler(stream_handler)
    file_handler_info = logging.FileHandler(logitiedosto_infoille, mode='w')
    file_handler_info.setFormatter(login_formaatti)
    file_handler_info.setLevel(logging.INFO)
    logi.addHandler(file_handler_info)
    file_handler_error = logging.FileHandler(logitiedosto_virheille, mode='w')
    file_handler_error.setFormatter(login_formaatti)
    file_handler_error.setLevel(logging.ERROR)
    logi.addHandler(file_handler_error)
    logi.setLevel(logging.INFO)
    return logi


loggeri = virhe_loggeri()


def terminoi_prosessi(signaali, frame):
    """ Terminointi """
    print('(SIGTERM) terminoidaan prosessi %s' % os.getpid())
    loggeri.info("Prosessi %s terminoitu klo %s." % (os.getpid(), datetime.datetime.now()))
    sys.exit()


def mqttyhdista(client, userdata, flags, rc):
    # print("Yhdistetty " + str(rc))
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    client.subscribe(RELE1_MQTTAIHE_1)  # tilaa aihe releelle 1
    client.subscribe(RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2
    client.subscribe(RELE3_MQTTAIHE_3)  # tilaa aihe releelle 3
    client.subscribe(RELE4_MQTTAIHE_4)  # tilaa aihe releelle 4
    return


def mqttviesti(client, userdata, message):
    """ Looppia suoritetaan aina kun aiheeseen julkaistaan viesti
    Muista laittaa mqtt-julkaisuun Retained = True, muutoin rele vain
    kay kerran paalla ja nollautuu!
    """
    viesti = int(message.payload)
    if (viesti < 0) or (viesti > 1):
        # print("Virheellinen arvo!")
        loggeri.error("Virheellinen arvo kutsussa!")
        return False
    """ Releelle ja aiheelle 1 """
    if message.topic == RELE1_MQTTAIHE_1:
        try:
            GPIO.output(RELE1_PINNI, viesti)
        except OSError as e:
            loggeri.error("Rele 1: virhe %s" % e)
            GPIO.cleanup()
            return False
    """ Releelle ja aiheelle 2 """
    if message.topic == RELE2_MQTTAIHE_2:
        try:
            GPIO.output(RELE2_PINNI, viesti)
        except OSError as e:
            loggeri.error("Rele 2: virhe %s" % e)
            GPIO.cleanup()
            return False
    """ Releelle ja aiheelle 3 """
    if message.topic == RELE3_MQTTAIHE_3:
        try:
            GPIO.output(RELE3_PINNI, viesti)
        except OSError as e:
            loggeri.error("Rele 3: virhe %s" % e)
            GPIO.cleanup()
            return False
    """ Releelle ja aiheelle 4 """
    if message.topic == RELE4_MQTTAIHE_4:
        try:
            GPIO.output(RELE4_PINNI, viesti)
        except OSError as e:
            loggeri.error("Rele4: virhe %s" % e)
            GPIO.cleanup()
            return False
    return  # mqttviesti


def relepaaluuppi():
    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    GPIO.setmode(GPIO.BCM)
    """  Releiden pinnien GPIO- alkuasetus, oletus alustus 0 """
    GPIO.setup(RELE1_PINNI, GPIO.OUT, initial=0)
    GPIO.setup(RELE2_PINNI, GPIO.OUT, initial=0)
    GPIO.setup(RELE3_PINNI, GPIO.OUT, initial=0)
    GPIO.setup(RELE4_PINNI, GPIO.OUT, initial=0)
    """ mqtt-objektin luominen """
    """ Tassa kaytetaan salaamatonta porttia ilman TLS:aa, vaihda tarvittaessa """
    mqttasiakas = mqtt.Client("2x2rele-broker")  # mqtt objektin luominen, tulla olla uniikki nimi
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttasiakas.on_message = mqttviesti  # maarita mita tehdaan kun viesti saapuu
    """ Suoritetaan looppia kunnes toiminta katkaistaan"""
    try:
        while True:
            mqttasiakas.loop_forever()
            time.sleep(0.1)
    except KeyboardInterrupt:
        loggeri.info("2x2-relescripti katkaistu kasin")
        GPIO.cleanup()
        pass


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    relepaaluuppi()
