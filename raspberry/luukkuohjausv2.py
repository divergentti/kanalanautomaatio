#!/usr/bin/env python3
"""
 Versioon 2 on lisätty auringon laskun laskenta, jolloin luukku voidaan sulkea esimerkiksi tunti
 auringonlaskun jälkeen, jolloin kanojen voi olettaa olevan kanalassa.

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


 7.9.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt  # mqtt kirjasto
import RPi.GPIO as GPIO
import subprocess  # shell-komentoja varten
import logging
import datetime
from dateutil import tz
from suntime import Sun, SunTimeException
import time  # loopin hidastusta varten, muuten CPU 25 %
from parametrit import LUUKKUAIHE, REEDPINNI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERIPORTTI, \
    REEDAIHE, REEDANTURI, LUUKKUANTURI, LONGITUDI, LATITUDI, ULKOLUUKKU_KIINNI_VIIVE

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

""" Objektien luonti """
mqttluukku = mqtt.Client(LUUKKUANTURI)  # mqtt objektin luominen
mqttreedrele = mqtt.Client(REEDANTURI)  # mqtt objektin luominen
aurinko = Sun(LATITUDI, LONGITUDI)

""" Globaalit muuttujat """
aiempiviesti = None  # suoritetaan mqtt-retained viestit vain kerran
suorituksessa = False  # onko luukun avaus tai sulku suorituksessa
aurinko_laskenut = False  # laskennallinen tieto auringon laskusta


def mqttyhdista(mqttluukku, userdata, flags, rc):
    print("Yhdistetty statuksella " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aihe
    mqttluukku.subscribe(LUUKKUAIHE)  # tilaa aihe luukun statukselle

def mqttluukku_pura_yhteys(mqttluukku, userdata, rc=0):
    logging.debug("Yhteys purettu: " + str(rc))
    mqttluukku.loop_stop()


def mqtt_luukku_viesti(mqttluukku, userdata, message):
    global aiempiviesti
    """ Mikäli tila on jo tämän scriptin toimesta muutettu, ei lähetetä uudelleen viestiä! """
    viesti = int(message.payload)
    print("Viesti %s, aiempiviesti %s" %(viesti, aiempiviesti))
    if (viesti < 0) or (viesti > 1):
        print("Virheellinen arvo!")
        logging.error('Virheellinen arvo mqtt_luukku_viesti-kutsulle')
        return False
    if (viesti == 0) and (viesti !=aiempiviesti):
        luukku_muutos(0)
        return True
    if (viesti == 1) and (viesti != aiempiviesti):
        print("Lahetaan luukulle auki")
        luukku_muutos(1)
        return True

def luukku_muutos(status):
    global aiempiviesti, suorituksessa
    """ Lähetetään uusiksi luukulle komento joko auki tai kiinni """
    if (status == 0) and (suorituksessa == False):
        print("Lahetaan luukulle kiinni")
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
        except OSError:
            print("Virhe %d" % OSError)
            logging.error('Luukkuohjaus OS-virhe %s' % OSError)
            return False
    if status ==1 and (suorituksessa == False):
        print("Lahetaan luukulle auki")
        try:
            suorituksessa = True
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-auki', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            time.sleep(31)  # luukun aukeamisaika
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-auki', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
            suorituksessa = False
            aiempiviesti = 1
        except OSError:
            print("Virhe %d" % OSError)
            logging.error('Luukkuohjaus OS-virhe %s' % OSError)
            return False


def reedMuutos(channel):
    global aiempiviesti  # verrataan mika tulisi olla luukun status
    global suorituksessa  # ollaanko juuri suorittamassa edellista toimintoa
    # 1 = reed on (eli magneetti irti), 0 = reed off (magneetti kiinni)
    if suorituksessa == True:
        print ("Suorituksessa, skipataan")
        return
    if GPIO.input(REEDPINNI):
        print ("Reed-kytkin on")
        if aiempiviesti != 0:
            print("Luukku tulisi olla auki, mutta reed-kytkimen mukaan se on kiinni!")
            logging.error('Luukkuohjaus: luukku tulisi olla auki, mutta reed-kytkimen mukaan se ei ole!')
        try:
            mqttreedrele.publish(REEDAIHE, payload=1, retain=True)
        except OSError:
            print("Virhe %d" % OSError)
            logging.error('Luukkuohjaus OS-virhe %s' % OSError)
            GPIO.cleanup()
            return False
        return 1
    else:
        print ("Reed-kytkin pois")
        if aiempiviesti != 1:
            print("Luukku tulisi olla kiinni, mutta reed-kytkimen mukaan se on auki!")
            logging.error('Luukkuohjaus: luukku tulisi olla kiinni, mutta reed-kytkimen mukaan se ei ole!')
        try:
            mqttreedrele.publish(REEDAIHE, payload=0, retain=True)
        except OSError:
            print("Virhe %d" % OSError)
            logging.error('Luukkuohjaus OS-virhe %s' % OSError)
            GPIO.cleanup()
            return False
        return 0

def alustus():
    mqttluukku.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    mqttluukku.on_message = mqtt_luukku_viesti  # maarita mita tehdaan kun viesti saapuu
    mqttluukku.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttluukku.on_disconnect = mqttluukku_pura_yhteys  # puretaan yhteys disconnectissa
    mqttluukku.connect(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttluukku.subscribe(LUUKKUAIHE)  # tilaa aihe
    try:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(REEDPINNI, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(REEDPINNI, GPIO.BOTH, callback=reedMuutos, bouncetime=20)

    except OSError:
        print("Virhe %d" %OSError)
        logging.error('Luukkuohjaus OS-virhe %s' % OSError)
        GPIO.cleanup()
        return False

def looppi():
    global aiempiviesti, suorituksessa
    alustus()  # alustetaan objektit
    ''' Päivämäärämuuttujat'''
    aikavyohyke = tz.tzlocal()

    while True:
        mqttluukku.loop_start()  # kuunnellaan jos tulee muutos luukun statukseen
        ''' Palauttaa UTC-ajan ilman astitimezonea'''
        auringon_lasku = aurinko.get_sunset_time().astimezone(aikavyohyke)
        aika_nyt = datetime.datetime.now()
        ''' Pythonin datetime naiven ja awaren vuoksi puretaan päivä ja aika osiin '''
        laskuaika_arvo = (auringon_lasku.time().hour * 60) + auringon_lasku.time().minute
        aika_nyt_arvo = (aika_nyt.hour * 60) + aika_nyt.minute
        ''' Montako minuuttia auringon laskun jälkeen luukku tulisi sulkea '''
        lisaa_minuutit = int(ULKOLUUKKU_KIINNI_VIIVE)
        pois_arvo = laskuaika_arvo + lisaa_minuutit

        ''' Auringon nousu tai laskulogiikka '''
        if laskuaika_arvo > aika_nyt_arvo:
            aurinko_laskenut = False
        else:
            aurinko_laskenut = True

        ''' Luukun sulkemislogiikka'''

        ''' Jos aurinko on laskenut, suljetaan luukku jos luukku on auki ja viiveaika saavutettu'''
        if (aurinko_laskenut == True) and (suorituksessa == False) and \
                (aiempiviesti == 1) and (aika_nyt_arvo >= pois_arvo):
            luukku_muutos(0)
            print("Aurinko laskenut ja viive saavutettu. Suljetaan luukku.")

        time.sleep(1) # CPU muuten 25 % jos ei ole hidastusta

if __name__ == "__main__":
    looppi()
