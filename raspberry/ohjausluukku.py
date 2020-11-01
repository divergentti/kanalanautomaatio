#!/usr/bin/env python3
"""
 Laskee auringonlaskun ja lähettää ULKOLUUKKU_KIINNI_VIIVE jälkeen komennon sulkea luukku.

 Scripti kuuntelee myös mqtt-viestiä siitä laitetaanko luukku pois tai päälle.

 Mikäli mqtt-viesti ohjaa luukun kiinni,lähetetään ennakolta tutkittu kaukosaatimen koodi vastaanottimeen
 käyttämällä FS1000A 433MHz lähetinmodulia.

 Lineaarimoottoria ohjaava kaukosäädintoimilaite on malliltaan KZ005-2 DC 9-30V Wireless Remote Control
 Kits Linear Actuator Motor Controller. Sille sopivat kaukosäätimen lähettämät koodit ovat:
 - koodi 3669736: #kiinni
 - koodi 3669729: #auki

 433MHz ohjaus kutsutaan erillista koodia crontabin vuoksi (aika-ajastus).

 Lisäksi scripti lukee reed-releen tilaa siitä onko luukku todella auennut vai eikö ole.
 Mikäli luukun aukeaminen tai sulkeutuminen kestää normaalia pidempään, voi se olla merkki
 luukun vioittumisesta. Reed releen status päivitetään mqtt:n avulla.


 1.11.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt  # mqtt kirjasto
import RPi.GPIO as GPIO
import subprocess  # shell-komentoja varten
import logging
import datetime
import os
import sys
import signal
from dateutil import tz
from suntime import Sun
import time
from parametrit import LUUKKUAIHE, REEDPINNI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERIPORTTI, \
    REEDAIHE, LUUKKUANTURI, LONGITUDI, LATITUDI, ULKOLUUKKU_KIINNI_VIIVE


""" Objektien luonti """
mqttluukku = mqtt.Client(LUUKKUANTURI)  # mqtt objektin luominen
aurinko = Sun(LATITUDI, LONGITUDI)

""" Globaalit muuttujat """
aiempiviesti = None  # suoritetaan mqtt-retained viestit vain kerran
suorituksessa = False  # onko luukun avaus tai sulku suorituksessa
aurinko_laskenut = False  # laskennallinen tieto auringon laskusta

''' Päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/ohjausluukku-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/ohjausluukku-virhe.log'):
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
    client.subscribe(LUUKKUAIHE)  # tilaa aihe luukun statukselle


def mqtt_pura_yhteys(client, userdata, rc=0):
    loggeri.info("%s: Purettu yhteys statuksella %s" % (datetime.datetime.now(), str(rc)))
    mqttluukku.loop_stop()


def mqtt_viesti(client, userdata, message):
    global aiempiviesti
    if message.topic == LUUKKUAIHE:
        """ Mikäli tila on jo tämän scriptin toimesta muutettu, ei lähetetä uudelleen viestiä! """
        viesti = int(message.payload)
        print("Viesti %s, aiempiviesti %s" % (viesti, aiempiviesti))
        if (viesti < 0) or (viesti > 1):
            print("Virheellinen arvo!")
            loggeri.error('%s: Virheellinen arvo mqtt_luukku_viesti-kutsulle!', datetime.datetime.now())
        if (viesti == 0) and (viesti != aiempiviesti):
            luukku_muutos(0)
        if (viesti == 1) and (viesti != aiempiviesti):
            luukku_muutos(1)


def luukku_muutos(status):
    global aiempiviesti, suorituksessa
    """ Lähetetään uusiksi luukulle komento joko auki tai kiinni """
    if (status == 0) and (suorituksessa is False):
        print("Lahetaan luukulle kiinni")
        loggeri.info("%s: Lahetaan luukulle kiinni", datetime.datetime.now())
        try:
            # samaa scrptia kutsutaan crobtabissa ajastettuna, siksi toteutus tama
            suorituksessa = True
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-kiinni', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            time.sleep(31)  # luukun aukeamisaika, eli toinen painallus
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-kiinni', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            suorituksessa = False
            aiempiviesti = 0
        except OSError as e:
            print("Virhe %s" % e)
            loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))
    if (status == 1) and (suorituksessa is False):
        print("Lahetaan luukulle auki")
        loggeri.info("%s: Lahetaan luukulle auki", datetime.datetime.now())
        try:
            suorituksessa = True
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-auki', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            time.sleep(31)  # luukun aukeamisaika
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-auki', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            suorituksessa = False
            aiempiviesti = 1
        except OSError as e:
            print("Virhe %s" % e)
            loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))


def reedmuutos(channel):
    global aiempiviesti  # verrataan mika tulisi olla luukun status
    global suorituksessa  # ollaanko juuri suorittamassa edellista toimintoa
    # 1 = reed on (eli magneetti irti), 0 = reed off (magneetti kiinni)
    if (suorituksessa is False) and (GPIO.input(REEDPINNI)):
        print("Reed-kytkin on")
        if aiempiviesti != 0:
            print("Luukku tulisi olla auki, mutta reed-kytkimen mukaan se on kiinni!")
            loggeri.error('%s: Luukkuohjaus: luukku tulisi olla auki, mutta reed-kytkimen mukaan se ei ole!',
                          datetime.datetime.now())
            try:
                mqttluukku.publish(REEDAIHE, payload=1, qos=1, retain=True)
            except OSError as e:
                print("Virhe %s" % e)
                loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))
                GPIO.cleanup()
                return False
            return 1
        elif aiempiviesti != 1:
            print("Luukku tulisi olla kiinni, mutta reed-kytkimen mukaan se on auki!")
            loggeri.error('%s: Luukkuohjaus: luukku tulisi olla kiinni, mutta reed-kytkimen mukaan se ei ole!',
                          datetime.datetime.now())
            try:
                mqttluukku.publish(REEDAIHE, payload=0, qos=1, retain=True)
            except OSError as e:
                print("Virhe %s" % e)
                loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))
                GPIO.cleanup()
                return False
            return 0


def alustus():
    mqttluukku.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttluukku.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttluukku.on_disconnect = mqtt_pura_yhteys  # puretaan yhteys disconnectissa
    mqttluukku.on_message = mqtt_viesti
    mqttluukku.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttluukku.loop_start()  # kuunnellaan jos tulee muutos luukun statukseen

    try:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(REEDPINNI, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(REEDPINNI, GPIO.BOTH, callback=reedmuutos, bouncetime=20)
    except OSError as e:
        print("Virhe %s" % e)
        loggeri.error('%s: Luukkuohjaus OS-virhe %s' % (datetime.datetime.now(), e))
        GPIO.cleanup()


def looppi():
    global aiempiviesti, suorituksessa, aurinko_laskenut
    alustus()

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

            ''' Montako minuuttia auringon laskun jälkeen luukku tulisi sulkea '''
            lisaa_minuutit = int(ULKOLUUKKU_KIINNI_VIIVE)
            luukku_sulje_klo = auringon_lasku_tanaan + datetime.timedelta(minutes=lisaa_minuutit)

            ''' Luukun sulkemislogiikka'''

            ''' Jos aurinko on laskenut, suljetaan luukku jos luukku on auki ja viiveaika saavutettu'''
            if (aurinko_laskenut is True) and (suorituksessa is False) and \
                    (aiempiviesti == 1) and aika_nyt >= luukku_sulje_klo:
                luukku_muutos(0)
                print("Aurinko laskenut ja viive saavutettu. Suljetaan luukku.")
                loggeri.info("%s: Aurinko laskenut ja viive saavutettu. Suljetaan luukku.", aika_nyt)
            time.sleep(1)  # CPU muuten 25 % jos ei ole hidastusta

        except KeyboardInterrupt:
            raise


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    looppi()
