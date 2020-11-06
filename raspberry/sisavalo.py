#!/usr/bin/env python3
""" 10.08.2020 Jari Hiltunen

Scripti lukee mqtt-palvelimelta valoisuusanturin arvoa ja mikäli se on alle 300 ja valojen tulisi olla päällä,
laitetaan valot kanalaan päälle. Mikäli valoisuus on yli 300, valoja ei tarvita.

Valojen päällelaitto tapahtuu tässä tapauksessa RELE1- aihetta kutsumalla, eli kanala/sisa/valaistus, joka on
määritetty parametrit.py-tiedostossa.

4.11.2020: Lisätty virheloggeri
"""

import time
import datetime
from dateutil import tz
import signal
import sys
import os
import paho.mqtt.client as mqtt  # mqtt kirjasto
import logging
from parametrit import AIHEVALOISUUS, SISAVALO_PAALLE, SISAVALO_POIS, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    MQTTSERVERIPORTTI, RELE1_MQTTAIHE_1, ANTURIVALONOHJAUS


''' Globaalit '''
valoisuus = 0
aikavyohyke = tz.tzlocal()

""" Objektien luonti """
mqttvaloisuus = mqtt.Client(ANTURIVALONOHJAUS)  # mqtt objektin luominen


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/sisavalo-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/sisavalo-virhe.log'):
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
    loggeri.info("Prosessi %s terminoitu klo %s." % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    sys.exit()


def mqttyhdista(client, userdata, flags, rc):
    # print("Yhdistetty statuksella " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aihe
    client.subscribe(AIHEVALOISUUS)  # tilaa aihe valoisuustiedon päivittymiselle


def mqtt_valoisuus_viesti(client, userdata, message):
    global valoisuus
    valoisuus = int(message.payload)
    print("Valoisuus %s" % valoisuus)
    return valoisuus


def alustus():
    mqttvaloisuus.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttvaloisuus.on_message = mqtt_valoisuus_viesti  # maarita mita tehdaan kun viesti saapuu
    mqttvaloisuus.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttvaloisuus.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttvaloisuus.subscribe(AIHEVALOISUUS)  # tilaa aihe


def looppi():
    global valoisuus
    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    alustus()  # alustetaan objektit
    mqttvaloisuus.loop_start()  # kuunnellaan jos tulee muutos valoisuuteen
    valo_paalla = 0

    while True:
        aika_nyt = datetime.datetime.now()
        ''' Mikäli tarvitset sekunnit tai kalenteripohjaisen valaistuksen, muokkaa seuraavia rivejä'''
        sisavalo_paalle = datetime.datetime.strptime(SISAVALO_PAALLE, "%H:%M")
        sisavalo_paalle = aika_nyt.replace(hour=sisavalo_paalle.time().hour, minute=sisavalo_paalle.time().minute,
                                           second=0, microsecond=0)
        sisavalo_pois = datetime.datetime.strptime(SISAVALO_POIS, "%H:%M")
        sisavalo_pois = aika_nyt.replace(hour=sisavalo_pois.time().hour, minute=sisavalo_pois.time().minute,
                                         second=0, microsecond=0)
        ''' Edelläolevilla riveillä ratkaistaan aikavertailuun tarvittavat muuttujat '''
        if (aika_nyt >= sisavalo_paalle) and (aika_nyt < sisavalo_pois) and (valoisuus < 300) and (valo_paalla == 0):
            # print ("Sisavalo paalle")
            loggeri.info("%s: Sisävalo päälle" % datetime.datetime.now().astimezone(aikavyohyke))
            try:
                mqttvaloisuus.publish(RELE1_MQTTAIHE_1, payload=1, qos=1, retain=True)
                valo_paalla = 1
            except OSError as e:
                loggeri.error('%s: Sisavalonohjaus OS-virhe %s' % (datetime.datetime.now().astimezone(aikavyohyke), e))
        if (aika_nyt >= sisavalo_pois) and (valo_paalla == 1):
            loggeri.info("%s: Sisävalo pois." % datetime.datetime.now().astimezone(aikavyohyke))
            try:
                mqttvaloisuus.publish(RELE1_MQTTAIHE_1, payload=0, qos=1, retain=True)
                valo_paalla = 0
            except OSError as e:
                loggeri.error('%s: Sisavalonohjaus OS-virhe %s' % (datetime.datetime.now().astimezone(aikavyohyke), e))
        time.sleep(1)  # CPU muuten 25 % jos ei ole hidastusta


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    looppi()
