#!/usr/bin/env python3

''' 10.08.2020 Jari Hiltunen

Scripti lukee mqtt-palvelimelta valoisuusanturin arvoa ja mikäli se on alle 300 ja valojen tulisi olla päällä,
laitetaan valot kanalaan päälle. Mikäli valoisuus on yli 300, valoja ei tarvita.

Valojen päällelaitto tapahtuu tässä tapauksessa RELE1- aihetta kutsumalla, eli kanala/sisa/valaistus, joka on
määritetty parametrit.py-tiedostossa.

'''

import time
import datetime
import paho.mqtt.client as mqtt  # mqtt kirjasto
import logging
from parametrit import AIHEVALOISUUS, SISAVALO_PAALLE, SISAVALO_POIS, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    MQTTSERVERIPORTTI, RELE1_MQTTAIHE_1, ANTURIVALONOHJAUS

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

''' Globaalit '''
valoisuus = 0

""" Objektien luonti """
mqttvaloisuus = mqtt.Client(ANTURIVALONOHJAUS)  # mqtt objektin luominen


def mqttyhdista(mqttvaloisuus, userdata, flags, rc):
    # print("Yhdistetty statuksella " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aihe
    mqttvaloisuus.subscribe(AIHEVALOISUUS)  # tilaa aihe valoisuustiedon päivittymiselle

def mqtt_valoisuus_viesti(mqttvaloisuus, userdata, message):
    global valoisuus
    valoisuus = int(message.payload)
    print("Valoisuus %s" %valoisuus)
    return valoisuus

def alustus():
    mqttvaloisuus.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttvaloisuus.on_message = mqtt_valoisuus_viesti  # maarita mita tehdaan kun viesti saapuu
    mqttvaloisuus.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttvaloisuus.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttvaloisuus.subscribe(AIHEVALOISUUS)  # tilaa aihe

def looppi():
    global valoisuus
    alustus()  # alustetaan objektit
    mqttvaloisuus.loop_start()  # kuunnellaan jos tulee muutos valoisuuteen
    valo_paalla = 0

    while True:
        aika_nyt =  datetime.datetime.now()
        ''' Mikäli tarvitset sekunnit tai kalenteripohjaisen valaistuksen, muokkaa seuraavia rivejä'''
        sisavalo_paalle = datetime.datetime.strptime(SISAVALO_PAALLE, "%H:%M")
        sisavalo_paalle = aika_nyt.replace(hour=sisavalo_paalle.time().hour, minute=sisavalo_paalle.time().minute,
                                      second=0, microsecond=0)
        sisavalo_pois = datetime.datetime.strptime(SISAVALO_POIS, "%H:%M")
        sisavalo_pois = aika_nyt.replace(hour=sisavalo_pois.time().hour, minute=sisavalo_pois.time().minute,
                                      second=0, microsecond=0)
        ''' Edelläolevilla riveillä ratkaistaan aikavertailuun tarvittavat muuttujat '''
        if (aika_nyt >= sisavalo_paalle) and (aika_nyt < sisavalo_pois) and (valoisuus < 300) and (valo_paalla == 0):
            print ("Sisavalo paalle")
            try:
                mqttvaloisuus.publish(RELE1_MQTTAIHE_1, payload=1, retain=True)
                valo_paalla = 1
            except OSError:
                print("Virhe %d" % OSError)
                logging.error('Sisavalonohjaus OS-virhe %s' % OSError)
        if (aika_nyt >= sisavalo_pois) and (valo_paalla == 1):
            print ("Sisavalo pois %s" %aika_nyt)
            try:
                mqttvaloisuus.publish(RELE1_MQTTAIHE_1, payload=0, retain=True)
                valo_paalla = 0
            except OSError:
                print("Virhe %d" % OSError)
                logging.error('Sisavalonohjaus OS-virhe %s' % OSError)
        time.sleep(1) # CPU muuten 25 % jos ei ole hidastusta

if __name__ == "__main__":
    looppi()
