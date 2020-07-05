# !/usr/bin/python3
"""
Scripti lukee DHT22-anturia kerran per 10s, laskee niista LUKUVALI-mukaisen
 keskiarvon ja lahettaa arvot mqtt-avulla brokerille.

Parametrit tuodaan paramterit.py-tiedostosta.

5.7.2020 Jari Hiltunen
"""
import paho.mqtt.client as mqtt # tuodaan mqtt kirjasto
# asennus pip3 install paho-mqtt
import time
import syslog  # syslogiin kirjoittamista varten
""" 
 Uuden adafruitin kanssa tarvittaisiin muiden komponenttien asennus:
 pip3 install RPI.GPIO
 pip3 install adafruit-blinka - ei tarvita
 pip3 install adafruit-circuitpython-dht  ei tarvita
 sudo apt-get install libgpiod2 ei tarvita
import board
 import adafruit_dht ei tarvita
"""
import Adafruit_DHT  # vanha toimiva adafruit-kirjasto
#  muuttujat tuodaan parametrit.py_tiedostosta
from parametrit import ANTURINIMI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERI, MQTTSERVERIPORTTI, \
    AIHELAMPO, AIHEKOSTEUS, DHT22PINNI, LUKUVALI
"""
IoT ja mqtt suhteen kannattaa kayttaa autentikointia ja mikali jarjestelma on 
julkisesti saavutettavissa, mielellaan salattua yhteytta.
"""
mqttanturi = mqtt.Client(ANTURINIMI)   # mqtt objektin luominen
mqttanturi.username_pw_set(MQTTKAYTTAJA, MQTTSALARI) # mqtt useri ja salari
mqttanturi.connect(MQTTSERVERI, port=MQTTSERVERIPORTTI, keepalive=60) # Yhteys brokeriin
# mqttanturi.loop_start() # Loopin kaynnistys on turha jos ei lueta arvoja

def liikaa_virheita():
    """ Suoritetaan kun virhelaskuri ylittaa 50 """
    syslog.syslog("DHT22-anturin luennassa on ollut ongelmia yli 50 kertaa!")
    return

def paaluuppi():
    """ Scripti lukee arvoja kerran 10s. listaan, josta lasketaan
        keskiarvo, joka lahetetaan palvelimelle. Nain valtytaan silta, etta
        jokin anturin poikkeava arvo joka jaisi valille -40 - 100 astetta paatyisi
        mqtt-sanomaan.
        DHT22-anturille minimi lukuvali on 2s. ja huomaa LUKUVALI/10 arvot,
        jossa jakaja = 10 (jos muutat, muuta jakajaakin)
    """
    print("Aloitetaan luku, arvot talllentuvat %s luentakerran valein" %(LUKUVALI/10))

    lampo_lista = []  # keskiarvon laskentaa varten
    kosteus_lista = []
    virhelaskuri = 0  # virhelaskentaa varten

    while True:
        try:
            kosteus, lampo = Adafruit_DHT.read_retry(22, DHT22PINNI)
            # estetaan vaarat arvot
            if (lampo is not None) and (lampo < 100) and (lampo > -40):
                lampo_lista.append(lampo)
                if len(lampo_lista) == (LUKUVALI/10):
                    lampo_keskiarvo = sum(lampo_lista) / len(lampo_lista)
                    lampo_keskiarvo = '{:.1f}'.format(lampo_keskiarvo)
                    print("Tallennettava lampokeskiarvo on: %s " % lampo_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHELAMPO, payload=lampo_keskiarvo, retain=True)
                    lampo_lista.clear()  # nollataan lista
            else:
                print (time.strftime("%H:%M:%S ") + "Lampotilatietoa ei saatavilla! %s kerta" %virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            if (kosteus is not None) and (kosteus >0) and (kosteus < 101):
                kosteus_lista.append((kosteus))
                if len(kosteus_lista) == (LUKUVALI/10):
                    kosteus_keskiarvo = sum(kosteus_lista) / len(kosteus_lista)
                    kosteus_keskiarvo = '{:.1f}'.format(kosteus_keskiarvo)
                    print("Tallennettava kosteuskeskiarvo on: %s " % kosteus_keskiarvo)
                    # julkaistaan keskiarvo mqtt
                    mqttanturi.publish(AIHEKOSTEUS, payload=kosteus_keskiarvo, retain=True)
                    kosteus_lista.clear()  # nollataan lista
            else:
                print(time.strftime("%H:%M:%S ") + "Kosteustietoa ei saatavilla! %s kerta" %virhelaskuri)
                virhelaskuri = virhelaskuri + 1
                if virhelaskuri >= 50:
                    liikaa_virheita()
                    virhelaskuri = 0
                    pass
            time.sleep(10) # luetaan arvoa 10s valein, minimi 2 s DHT22 anturille
        except RuntimeError as error:
            print(error.args[0])

if __name__ == "__main__":
    paaluuppi()
