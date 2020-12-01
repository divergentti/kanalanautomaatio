#!/usr/bin/env python3
"""
 Komentaa luukkua avautumaan, jos on aika avata luukku. Huomaa, että luukku ei aukea, jos lämpötila ei ole riittävä!
 Lämpötila tarkistetaan sekä tässä scriptissä että itse avauscriptissä.

 Laskee auringonlaskun ja lähettää ULKOLUUKKU_KIINNI_VIIVE jälkeen komennon sulkea luukku.

 30.11.2020 Jari Hiltunen
 1.12.2020 Lisätty luukun statuksen päivitys mqtt-kautta. Huom! Yhteysongelmissa lisää brokerin päähän debug!

"""

import paho.mqtt.client as mqtt  # mqtt kirjasto
import logging
import datetime
import os
import sys
import signal
from dateutil import tz
from suntime import Sun
import time
from parametrit import LUUKKUAIHE, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERIPORTTI, \
    LONGITUDI, LATITUDI, ULKOLUUKKU_KIINNI_VIIVE, LUUKKU_AVAUSAIKA_MA_PE, LUUKKU_AVAUSAIKA_LA_SU


""" Objektien luonti """
mqttobjekti = mqtt.Client('luukku-aukikiinni')  # mqtt objektin luominen
aurinko = Sun(LATITUDI, LONGITUDI)


''' Päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()

''' Globaalit '''
luukku_auki = None


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/luukkuaukikiinni-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/luukkuaukikiinni-virhe.log'):
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
    print("Yhdistetty statuksella " + str(rc))
    loggeri.info("%s: Yhdistetty statuksella %s" % (datetime.datetime.now(), str(rc)))
    # Yhdistetaan brokeriin ja tilataan aihe
    client.subscribe('kanala/ulko/luukku')


def mqtt_pura_yhteys(client, userdata, rc=0):
    loggeri.info("%s: Purettu yhteys statuksella %s" % (datetime.datetime.now(), str(rc)))
    client.loop_stop()


def mqtt_viesti(client, userdata, message):
    global luukku_auki
    print(message.payload)
    if int(message.payload) == 1:
        luukku_auki = True
    elif int(message.payload) == 0:
        luukku_auki = False


def alustus():
    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))
    mqttobjekti.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttobjekti.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttobjekti.on_message = mqtt_viesti
    mqttobjekti.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttobjekti.loop_start()


def looppi():
    alustus()
    ma_pe_tunnit, ma_pe_minutit = map(int, LUUKKU_AVAUSAIKA_MA_PE.split(':'))
    la_su_tunnit, la_su_minutit = map(int, LUUKKU_AVAUSAIKA_LA_SU.split(':'))
    sulkuviive = 32  # sekuntia

    while True:
        try:
            ''' Huom! Palauttaa UTC-ajan ilman astitimezonea'''
            auringon_nousu_tanaan = aurinko.get_sunrise_time().astimezone(aikavyohyke)
            ''' Lisätään auringon laskuun 30 minuuttia jotta ehtii tulla pimeää '''
            # auringon_lasku_tanaan = aurinko.get_sunset_time().astimezone(aikavyohyke) + datetime.timedelta(minutes=30)
            auringon_lasku_tanaan = aurinko.get_sunset_time().astimezone(aikavyohyke)
            auringon_nousu_huomenna = aurinko.get_sunrise_time().astimezone(aikavyohyke) + datetime.timedelta(days=1)
            ''' Mikäli käytät utc-aikaa, käytä alla olevaa riviä, muista vaihtaa datetime-kutusissa tzInfo=None'''
            aika_nyt = datetime.datetime.now().astimezone(aikavyohyke)
            ''' Auringon nousu tai laskulogiikka '''
            if (aika_nyt >= auringon_lasku_tanaan) and (aika_nyt < auringon_nousu_huomenna):
                aurinko_laskenut = True
            elif aika_nyt < auringon_nousu_tanaan:
                aurinko_laskenut = True
            else:
                aurinko_laskenut = False

            ''' Ollaanko viikolla vai viikonlopussa '''
            viikonpaiva = datetime.datetime.today().weekday()
            if viikonpaiva < 5:
                viikolla = True
            else:
                viikolla = False

            ''' Montako minuuttia auringon laskun jälkeen luukku tulisi sulkea jotta kanat on sisällä '''
            lisaa_minuutit = int(ULKOLUUKKU_KIINNI_VIIVE)
            luukku_sulje_klo = auringon_lasku_tanaan + datetime.timedelta(minutes=lisaa_minuutit)

            ''' Luukun avauslogiikka'''
            ma_pe_auki = aika_nyt.replace(hour=ma_pe_tunnit, minute=ma_pe_minutit)
            la_su_auki = aika_nyt.replace(hour=la_su_tunnit, minute=la_su_minutit)

            if (viikolla is True) and (aika_nyt >= ma_pe_auki) and (aika_nyt.hour < 12) and (luukku_auki is False):
                mqttobjekti.publish(LUUKKUAIHE, payload=1, qos=1, retain=True)
                time.sleep(sulkuviive)
                loggeri.info("%s: Avataan luukku MA-PE ajan mukaisesti.", aika_nyt)
            if (viikolla is False) and (aika_nyt >= la_su_auki) and (aika_nyt.hour < 12) and (luukku_auki is False):
                mqttobjekti.publish(LUUKKUAIHE, payload=1, qos=1, retain=True)
                time.sleep(sulkuviive)
                loggeri.info("%s: Avataan luukku LA-SU ajan mukaisesti.", aika_nyt)

            ''' Luukun sulkemislogiikka '''

            ''' Jos aurinko on laskenut, suljetaan luukku jos luukku on auki ja viiveaika saavutettu'''
            if (aurinko_laskenut is True) and (aika_nyt >= luukku_sulje_klo) and (luukku_auki is True):
                mqttobjekti.publish(LUUKKUAIHE, payload=0, qos=1, retain=True)
                time.sleep(sulkuviive)
                loggeri.info("%s: Aurinko laskenut ja viive saavutettu. Suljetaan luukku.", aika_nyt)

            time.sleep(1)  # CPU muuten 25 % jos ei ole hidastusta ja mqtt brokeri kerkiää käsitellä tilanteen

        except KeyboardInterrupt:
            raise


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    looppi()
