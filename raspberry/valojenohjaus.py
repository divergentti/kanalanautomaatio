#!/usr/bin/env python3
"""
Valojen varsinainen ohjaus tapahtuu mqtt-viesteillä, joita voivat lähettää esimerkiksi lähestymisanturit,
kännykän sovellus tai jokin muu IoT-laite.

Ulkotiloissa valoja on turha sytyttää, jos valoisuus riittää muutenkin. Tieto valoisuudesta saadaan mqtt-kanaviin
valoantureilla, mutta lisätieto auringon nousu- ja laskuajoista voi olla myös tarpeen.

Tämä scripti laskee auringon nousu- ja laskuajat ja lähettää mqtt-komennon valojen päälle kytkemiseen tai sammuttamiseen.

Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

30.8.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt # mqtt kirjasto
import time
# import syslog  # Syslogiin kirjoittamista varten
import datetime
import logging
from suntime import Sun, SunTimeException
from parametrit import LATITUDI, LONGITUDI, MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALO_PAALLAPITO
logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

aurinko = Sun(LATITUDI, LONGITUDI)
''' 
Longitudin ja latitudin saat syöttämällä osoitteen esimerkiksi Google Mapsiin.
'''

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE1_MQTTAIHE_1)  # tilaa aihe releelle 1
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2

def ohjausluuppi():
    """ Tassa kaytetaan salaamatonta porttia ilman TLS:aa, vaihda tarvittaessa """
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttasiakas = mqtt.Client("valojenohjaus-laskettu")  # mqtt objektin luominen, tulla olla uniikki nimi
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    valot_paalla = False
    """ Suoritetaan looppia kunnes toiminta katkaistaan"""
    while True:
        try:
            auringon_nousu = aurinko.get_sunrise_time()
            auringon_lasku = aurinko.get_sunset_time()
            aika_nyt = datetime.datetime.utcnow()
            lisa_aika = auringon_lasku + datetime.timedelta(minutes=VALO_PAALLAPITO)
            print('Aika nyt {}, aurinko nousi {} ja laskee {} UTC'.
                format(aika_nyt.strftime('%H:%M'), auringon_nousu.strftime('%H:%M'), auringon_lasku.strftime('%H:%M')))
            ''' Sytytetään valot ja pidetään valoja päällä laskun jälkeen VALO_PAALLAPITO minuuttia'''
            if (aika_nyt.replace(tzinfo=None) >= auringon_nousu.replace(tzinfo=None)) and \
                (aika_nyt.replace(tzinfo=None) < auringon_lasku.replace(tzinfo=None)):
                print("Aurinko on noussut. Auringon laskuun %s " % (auringon_lasku.replace(tzinfo=None) - aika_nyt.replace(tzinfo=None)))
            ''' Tarkistetaan tulisiko valojen olla päällä'''
            if (aika_nyt.replace(tzinfo=None) < lisa_aika.replace(tzinfo=None)) and \
                    (aika_nyt.replace(tzinfo=None) < auringon_nousu.replace(tzinfo=None)) and \
                    valot_paalla == False:
                print("Aurinko on laskenut. Auringon nousuun %s " % (auringon_nousu.replace(tzinfo=None) - aika_nyt.replace(tzinfo=None)))
                ''' Lähetetään komento valojen päällelaittoon '''
                try:
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, payload=1, retain=True)
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=1, retain=True)
                    valot_paalla = True
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            ''' Päälläoloaika ylittynyt'''
            if (aika_nyt.replace(tzinfo=None) >= lisa_aika.replace(tzinfo=None)) and \
                    valot_paalla == True:
                print("Laitetaan valot pois") 
                ''' Lähetetään komento valojen poislaittoon '''
                try:
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, payload=0, retain=True)
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=0, retain=True)
                    valot_paalla = False
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            time.sleep(10) # suoritetaan 10s valein

        except SunTimeException as e:
            logging.error("Virhe valojenohjaus.py - (tarkista longitudi ja latitudi): {0}.".format(e))

if __name__ == "__main__":
    ohjausluuppi()
