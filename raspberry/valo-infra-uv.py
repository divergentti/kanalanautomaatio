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

"""

import time
import SI1145.SI1145 as SI1145
import paho.mqtt.client as mqtt  # asennus pip3 install paho-mqtt
import time
import syslog # syslogiin kirjoittamista varten
from parametrit import VALOANTURINIMI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERI, MQTTSERVERIPORTTI,\
    AIHEVALOISUUS, AIHEUV, AIHEINFRAPUNA

''' Objektien luonti '''
valosensori = SI1145.SI1145()
mqttanturi = mqtt.Client(VALOANTURINIMI)   # mqtt objektin luominen
mqttanturi.username_pw_set(MQTTKAYTTAJA, MQTTSALARI) # mqtt useri ja salari
mqttanturi.connect(MQTTSERVERI, port=MQTTSERVERIPORTTI, keepalive=60) # Yhteys brokeriin

def liikaa_virheita():
    """ Suoritetaan kun virhelaskuri ylittaa 50 """
    syslog.syslog("Valoanturin luennassa on ollut ongelmia yli 50 kertaa!")
    return

def paaluuppi():
    """ Scripti lukee arvoja kerran 10s. listaan, josta lasketaan
        keskiarvo, joka lahetetaan palvelimelle. """
    valoisuus_lista = []  # keskiarvon laskentaa varten
    infrapuna_lista = []
    uv_lista = []

    virhelaskuri = 0  # virhelaskentaa varten

    while True:
        try:
            valoisuus = valosensori.readVisible()
            infrapuna = valosensori.readIR()
            uv = valosensori.readUV()
            uvIndeksi = uv / 100.0

            # estetaan vaarat arvot
            if (valoisuus is not None):
                print('Valoisuus: %s' %valoisuus)
                valoisuus_lista.append(valoisuus)
                if len(valoisuus_lista) == 6:
                    valoisuus_keskiarvo = sum(valoisuus_lista) / len(valoisuus_lista)
                    valoisuus_keskiarvo = '{:.1f}'.format(valoisuus_keskiarvo)
                    print("Tallennettava valoisuusarvo on: %s " % valoisuus_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEVALOISUUS, payload=valoisuus_keskiarvo, retain=True)
                    valoisuus_lista.clear()  # nollataan lista
            else:
                print (time.strftime("%H:%M:%S ") + "Valoisuustietoa ei saatavilla! %s kerta" %virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            if (infrapuna is not None):
                print('Infrapuna: %s' %infrapuna)
                infrapuna_lista.append((infrapuna))
                if len(infrapuna_lista) == 6:
                    infrapuna_keskiarvo = sum(infrapuna_lista) / len(infrapuna_lista)
                    infrapuna_keskiarvo = '{:.1f}'.format(infrapuna_keskiarvo)
                    print("Tallennettava infrapunakeskiarvo on: %s " % infrapuna_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEINFRAPUNA, payload=infrapuna_keskiarvo, retain=True)
                    infrapuna_lista.clear()  # nollataan lista
            else:
                print(time.strftime("%H:%M:%S ") + "Infrapunatietoa ei saatavilla! %s kerta" % virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            if (uv is not None):
                print('UV: %s ja UvIndeksi: %s' % (uv, uvIndeksi))
                uv_lista.append((uvIndeksi))
                if len(uv_lista) == 6:
                    uv_keskiarvo = sum(uv_lista) / len(uv_lista)
                    uv_keskiarvo = '{:.2f}'.format(uv_keskiarvo)
                    print("Tallennettava uv-keskiarvo on: %s " % uv_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEUV, payload=uv_keskiarvo, retain=True)
                    uv_lista.clear()  # nollataan lista
            else:
                print(time.strftime("%H:%M:%S ") + "UV-tietoa ei saatavilla! %s kerta" %virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            time.sleep(10) # luetaan arvoa 10s valein
        except RuntimeError as error:
            print(error.args[0])

if __name__ == "__main__":
    paaluuppi()
