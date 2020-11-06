#!/usr/bin/python
""" 27.7.2020 Jari Hiltunen
    Raspberryn I2C väylän käynnistys:
    - sudo apt-get install -y python-smbus
    - sudo apt-get install -y i2c-tools
    - sudo raspi-config ja sieltä 5 Intergacing options "install i2c support for the ARM core and linux kernel"
    - bootti
    - komennolla sudo i2cdetect -y 1 näet mitkä laitteet on kytketty i2c-väylään

    SI1145-kytkentä: +3v -> VCC, GND -> GND, Raspberry GPIO2(SDA, pinni 3) -> SDA, GPIO3 (SCL, pinni 5) - SCL

    SI1145 osalta hyödynnettävä kirjasto https://github.com/THP-JOE/Python_SI1145
    Lataa zip, asenna komennolla python3 setup.py install

    29.10.2020: lisätty virheloggeri

"""

import time
import SI1145.SI1145 as SI1145
import paho.mqtt.client as mqtt  # asennus pip3 install paho-mqtt
import time
import sys
import datetime
from dateutil import tz
import signal
import os
import logging
from parametrit import VALOANTURINIMI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERI, MQTTSERVERIPORTTI,\
    AIHEVALOISUUS, AIHEUV, AIHEINFRAPUNA

''' Objektien luonti '''
valosensori = SI1145.SI1145()
mqttanturi = mqtt.Client(VALOANTURINIMI)   # mqtt objektin luominen


''' Globaalit päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/valoisuus-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/valoisuus-virhe.log'):
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


def liikaa_virheita():
    """ Suoritetaan kun virhelaskuri ylittaa 50 """
    loggeri.error("Valoanturin luennassa on ollut ongelmia yli 50 kertaa!")
    time.sleep(60)


def mqttyhdista(client, userdata, flags, rc):
    print("Yhdistetty statuksella " + str(rc))
    loggeri.info("%s: Yhdistetty statuksella %s" % (datetime.datetime.now(), str(rc)))


def mqtt_pura_yhteys(client, userdata, rc=0):
    loggeri.info("%s: Purettu yhteys statuksella %s" % (datetime.datetime.now(), str(rc)))


def alustus():
    mqttanturi.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttanturi.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttanturi.on_disconnect = mqtt_pura_yhteys  # puretaan yhteys disconnectissa
    mqttanturi.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin


def paaluuppi():
    """ Scripti lukee arvoja kerran 10s. listaan, josta lasketaan
        keskiarvo, joka lahetetaan palvelimelle. """
    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    alustus()
    valoisuus_lista = []  # keskiarvon laskentaa varten
    infrapuna_lista = []
    uv_lista = []
    virhelaskuri = 0  # virhelaskentaa varten

    while True:
        try:
            valoisuus = valosensori.readVisible()
            infrapuna = valosensori.readIR()
            uv = valosensori.readUV()
            uvindeksi = uv / 100.0
            if mqttanturi.is_connected() is False:
                mqttanturi.reconnect()
            # estetaan vaarat arvot
            if valoisuus is not None:
                # print('Valoisuus: %s' % valoisuus)
                valoisuus_lista.append(valoisuus)
                if len(valoisuus_lista) == 6:
                    valoisuus_keskiarvo = sum(valoisuus_lista) / len(valoisuus_lista)
                    valoisuus_keskiarvo = '{:.1f}'.format(valoisuus_keskiarvo)
                    # print("Tallennettava valoisuusarvo on: %s " % valoisuus_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEVALOISUUS, payload=valoisuus_keskiarvo, retain=True)
                    valoisuus_lista.clear()  # nollataan lista
            else:
                print(time.strftime("%H:%M:%S ") + "Valoisuustietoa ei saatavilla! %s kerta" % virhelaskuri)
                loggeri.error((time.strftime("%H:%M:%S ") + "Valoisuustietoa ei saatavilla! %s kerta" % virhelaskuri))
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            if infrapuna is not None:
                # print('Infrapuna: %s' % infrapuna)
                infrapuna_lista.append(infrapuna)
                if len(infrapuna_lista) == 6:
                    infrapuna_keskiarvo = sum(infrapuna_lista) / len(infrapuna_lista)
                    infrapuna_keskiarvo = '{:.1f}'.format(infrapuna_keskiarvo)
                    # print("Tallennettava infrapunakeskiarvo on: %s " % infrapuna_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEINFRAPUNA, payload=infrapuna_keskiarvo, retain=True)
                    infrapuna_lista.clear()  # nollataan lista
            else:
                # print(time.strftime("%H:%M:%S ") + "Infrapunatietoa ei saatavilla! %s kerta" % virhelaskuri)
                loggeri.error(time.strftime("%H:%M:%S ") + "Infrapunatietoa ei saatavilla! %s kerta" % virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            if uv is not None:
                # print('UV: %s ja UvIndeksi: %s' % (uv, uvindeksi))
                uv_lista.append(uvindeksi)
                if len(uv_lista) == 6:
                    uv_keskiarvo = sum(uv_lista) / len(uv_lista)
                    uv_keskiarvo = '{:.2f}'.format(uv_keskiarvo)
                    # print("Tallennettava uv-keskiarvo on: %s " % uv_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEUV, payload=uv_keskiarvo, retain=True)
                    uv_lista.clear()  # nollataan lista
            else:
                # print(time.strftime("%H:%M:%S ") + "UV-tietoa ei saatavilla! %s kerta" % virhelaskuri)
                loggeri.error((time.strftime("%H:%M:%S ") + "UV-tietoa ei saatavilla! %s kerta" % virhelaskuri))
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            time.sleep(10)  # luetaan arvoa 10s valein
        except RuntimeError as error:
            loggeri.error(error.args[0])
            # print(error.args[0])


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    paaluuppi()
