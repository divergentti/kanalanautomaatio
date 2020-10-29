#!/usr/bin/env python3
# Kutsutaan crontabista, argumenttina numero väliltä 0 -3 
# 10 20 * * 1,2,3,4,5,6,0 python3 /home/pi/Kanala/puhallin.py 2 >/dev/null 2>&1
# 30 20 * * 1,2,3,4,5,6,0 python3 /home/pi/Kanala/puhallin.py 0 >/dev/null 2>&1
# ohjaa mqtt-viesteilla tassa tapauksessa reletta, joka ohjaa kanalan puhallinta
# Jari Hiltunen 14.6.2020
# parametrina releen ohjaustieto, joka voi olla:
# 0 = molemmat releet pois
# 1 = rele 1 on, rele 2 off
# 2 = molemmat on
# 3 = rele 1 off, rele 2 on

import paho.mqtt.client as mqtt
import logging
import sys
from parametrit import MQTTSERVERI, MQTTSERVERIPORTTI, MQTTKAYTTAJA, MQTTSALARI


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/puhallin-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/info/puhallin-virhe.log'):
    logi = logging.getLogger(login_nimi)
    login_formaatti = logging.Formatter(login_formaatti)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(login_formaatti)
    logi.addHandler(stream_handler)
    file_handler_info = logging.FileHandler(logitiedosto_infoille, mode='a')
    file_handler_info.setFormatter(login_formaatti)
    file_handler_info.setLevel(logging.INFO)
    logi.addHandler(file_handler_info)
    file_handler_error = logging.FileHandler(logitiedosto_virheille, mode='a')
    file_handler_error.setFormatter(login_formaatti)
    file_handler_error.setLevel(logging.ERROR)
    logi.addHandler(file_handler_error)
    logi.setLevel(logging.INFO)
    return logi


loggeri = virhe_loggeri()


def yhdista_mqtt(client, userdata, flags, rc):
    if client.is_connected() is False:
        try:
            client.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, 60, bind_address="")  # yhdista mqtt-brokeriin
        except OSError as e:
            loggeri.error("MQTT-palvelinongelma %s", e)
            raise Exception("MQTT-palvelinongelma! %s" % e)
        print("Yhdistetty statuksella: " + str(rc))
        loggeri.info("Yhdistetty statuksella: " + str(rc))
    """ Tilataan aiheet mqtt-palvelimelle. [0] ohjausobjekteissa tarkoittaa liikeanturia """
    # mqttvalot.subscribe("$SYS/#")


viesti = sys.argv[1]    # scriptin argumentti 1

# suoritetaan Raspberrylla
client = mqtt.Client("puhaltimen-ohjaus")
client.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)
client.connect(MQTTSERVERI, MQTTSERVERIPORTTI, 60, bind_address="")    # yhdista mqtt-brokeriin
aihe = "kanala/sisa/puhallin"   # aihe jolla status julkaistaan


# Lahetetaan mqtt-brokerille tieto
if (int(viesti) >= 0) and (int(viesti) < 4):
    statustieto = viesti
    try:
        client.publish(aihe, payload=str(statustieto), qos=1, retain=True)
        print("Releen ohjaus %s lahetetty" % statustieto)
        loggeri.info("Releen ohjaus %s lahetetty" % statustieto)
    except OSError:
        print("Ongelma lahetyksessa!")
        loggeri.error("Ongelma lahetyksessa!")
        pass
else:
    print("Arvo valilta 0 -3 kiitos!")
    loggeri.error("Arvo valilta 0 -3 kiitos!")
