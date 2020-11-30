""" Lukee reed-releen tilaa ja vertaa sitä luukun statusviestiin. Mikäli luukku on avattu ja reed mukaan luukku
    ei ole auki, kirjataan siitä virhe. Muuten kirjataan vain reedin ja luukun avauskäskyn välisen ajan erotus.

30.11.2020 Jari Hiltunen
"""


import paho.mqtt.client as mqtt  # mqtt kirjasto
import RPi.GPIO as GPIO
import logging
import datetime
import os
import sys
import signal
from dateutil import tz
import time

from parametrit import LUUKKUAIHE, REEDPINNI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERIPORTTI, \
     REEDAIHE

''' Päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()

""" Globaalit muuttujat """
reed_muutos_aika = datetime.datetime.now()
luukku_muutos_aika = datetime.datetime.now()
luukku_auki = None
reed_auki = None
aiempi_viesti = None
tilamuutos_havaittu = None


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/ohjausreed-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/ohjausreed-virhe.log'):
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

""" Objektien luonti """
mqttclientti = mqtt.Client("ohjaus-reed")  # mqtt objektin luominen


def terminoi_prosessi(signaali, frame):
    """ Terminointi """
    print('(SIGTERM) terminoidaan prosessi %s' % os.getpid())
    loggeri.info("Prosessi %s terminoitu klo %s." % (os.getpid(), datetime.datetime.now()))
    sys.exit()


def mqttyhdista(client, userdata, flags, rc):
    print("Yhdistetty statuksella " + str(rc))
    loggeri.info("%s: Yhdistetty statuksella %s" % (datetime.datetime.now(), str(rc)))
    # Yhdistetaan brokeriin ja tilataan aihe
    client.subscribe(LUUKKUAIHE)  # tilaa aihe luukun statukselle


def mqtt_pura_yhteys(client, userdata, rc=0):
    loggeri.info("%s: Purettu yhteys statuksella %s" % (datetime.datetime.now(), str(rc)))
    mqttclientti.loop_stop()


def mqtt_viesti(client, userdata, message):
    global luukku_auki, luukku_muutos_aika, aiempi_viesti, tilamuutos_havaittu
    if message.topic == LUUKKUAIHE:
        viesti = int(message.payload)
        if (viesti == 0) and (aiempi_viesti != 0):
            luukku_auki = False
            tilamuutos_havaittu = True
            luukku_muutos_aika = datetime.datetime.now().astimezone(aikavyohyke)
        elif (viesti == 1) and (aiempi_viesti != 1):
            luukku_auki = True
            tilamuutos_havaittu = True
            luukku_muutos_aika = datetime.datetime.now().astimezone(aikavyohyke)


def reedmuutos(channel):
    global reed_muutos_aika, reed_auki, tilamuutos_havaittu
    # 1 = reed on (eli magneetti irti), 0 = reed off (magneetti kiinni)
    if GPIO.input(REEDPINNI) == 0:
        reed_muutos_aika = datetime.datetime.now().astimezone(aikavyohyke)
        reed_auki = False
        tilamuutos_havaittu = True
        try:
            mqttclientti.publish(REEDAIHE, payload=0, qos=1, retain=True)
        except OSError as e:
            print("Virhe %s" % e)
            loggeri.error('%s: Reed OS-virhe %s' % (datetime.datetime.now(), e))
    elif GPIO.input(REEDPINNI) == 1:
        reed_muutos_aika = datetime.datetime.now().astimezone(aikavyohyke)
        reed_auki = True
        tilamuutos_havaittu = True
        try:
            mqttclientti.publish(REEDAIHE, payload=1, qos=1, retain=True)
        except OSError as e:
            print("Virhe %s" % e)
            loggeri.error('%s: Reed OS-virhe %s' % (datetime.datetime.now(), e))


def alustus():
    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    mqttclientti.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttclientti.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttclientti.on_message = mqtt_viesti
    mqttclientti.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttclientti.loop_start()  # kuunnellaan jos tulee muutos luukun statukseen

    try:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(REEDPINNI, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(REEDPINNI, GPIO.BOTH, callback=reedmuutos, bouncetime=20)
    except OSError as e:
        print("Virhe %s" % e)
        loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))
        GPIO.cleanup()


def looppi():
    global tilamuutos_havaittu
    alustus()  # alustetaan objektit
    avausviive = 32  # sekuntia

    while True:
        if tilamuutos_havaittu is True:
            if (luukku_auki is True) and (reed_auki is True) and ((luukku_muutos_aika - reed_muutos_aika).seconds
                                                                  < avausviive):
                ''' Vertaa aikoja '''
                loggeri.info("%s: Luukku avattu ok. Kesto luukku auki - reed auki: %s"
                         % (datetime.datetime.now().astimezone(aikavyohyke), luukku_muutos_aika - reed_muutos_aika))
                tilamuutos_havaittu = False
            elif (luukku_auki is True) and (reed_auki is True) and ((luukku_muutos_aika - reed_muutos_aika).seconds
                                                                    >= avausviive):
                ''' Avaus kesti liiän pitkään '''
                loggeri.info("%s: Luukku avattu ok. Kesto liian pitkä: %s"
                         % (datetime.datetime.now().astimezone(aikavyohyke), luukku_muutos_aika - reed_muutos_aika))
                tilamuutos_havaittu = False
            elif (luukku_auki is False) and (reed_auki is False) and ((luukku_muutos_aika - reed_muutos_aika).seconds
                                                                      < avausviive):
                ''' Vertaa aikoja '''
                loggeri.info("%s: Luukku suljettu ok. Kesto luukku kiinni - reed kiinni: %s"
                         % (datetime.datetime.now().astimezone(aikavyohyke), luukku_muutos_aika - reed_muutos_aika))
                tilamuutos_havaittu = False
            elif (luukku_auki is False) and (reed_auki is False) and ((luukku_muutos_aika - reed_muutos_aika).seconds
                                                                      >= avausviive):
                ''' Vertaa aikoja '''
                loggeri.info("%s: Luukku suljettu ok. Kesto liian pitkä: %s"
                         % (datetime.datetime.now().astimezone(aikavyohyke), luukku_muutos_aika - reed_muutos_aika))
                tilamuutos_havaittu = False
            elif (luukku_auki is False) and (reed_auki is True):
                ''' Virhe'''
                loggeri.error("%s: Reed-kytkimen mukaan luukun pitäisi olla kiinni mutta reedin mukaan se on auki!",
                              datetime.datetime.now().astimezone(aikavyohyke))
                tilamuutos_havaittu = False
            elif (luukku_auki is True) and (reed_auki is False):
                ''' Virhe '''
                loggeri.error("%s: Reed-kytkimen mukaan luukun pitäisi olla auki mutta reedin mukaan se on kiinni!",
                              datetime.datetime.now().astimezone(aikavyohyke))
                tilamuutos_havaittu = False

        time.sleep(1)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    looppi()
