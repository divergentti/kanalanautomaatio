""" ESP32-Wroom-NodeMCU ja vastaaville (micropython)

    27.8.2020: Jari Hiltunen

    PIR HC-SR501-sensorille:
    Luetaan liiketunnistimelta tulevaa statustietoa, joko pinni päällä tai pois.
    Mikäli havaitaan liikettä, havaitaan keskeytys ja tämä tieto välitetään mqtt-brokerille.

    MQTT-brokerissa voi olla esimerkiksi ledinauhoja ohjaavat laitteet tai muut toimet, joita
    liiketunnistuksesta tulee aktivoida. Voit liittää tähän scriptiin myös releiden ohjauksen,
    jos ESP32 ohjaa samalla myös releitä.

    MQTT hyödyntää valmista kirjastoa umqttsimple.py joka on ladattavissa:
    https://github.com/micropython/micropython-lib/tree/master/umqtt.simple


"""
import time
from time import sleep
import utime
import machine # tuodaan koko kirjasto
from machine import Pin
from umqttsimple import MQTTClient
import network
import gc

gc.enable()  # aktivoidaan automaattinen roskankeruu

# asetetaan hitaampi kellotus 20MHz, 40MHz, 80Mhz, 160MHz or 240MHz
machine.freq(80000000)
print ("Prosessorin nopeus asetettu: %s" %machine.freq())

# globaalit
liike = False

# Raspberry WiFi on huono ja lisaksi raspin pitaa pingata ESP32 jotta yhteys toimii!
sta_if = network.WLAN(network.STA_IF)

# tuodaan parametrit tiedostosta parametrit.py
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
    MQTT_SALASANA, PIR_PINNI, PIR_LIIKE_LOPPUAIKA, AIHE_LIIKETUNNISTIN

client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

# Liikesensorin pinni
pir = Pin(PIR_PINNI, Pin.IN)

def ratkaise_aika():
    (vuosi, kuukausi, kkpaiva, tunti, minuutti, sekunti, viikonpva, vuosipaiva) = utime.localtime()
    paivat = {0: "Ma", 1: "Ti", 2: "Ke", 3: "To", 4: "Pe", 5: "La", 6: "Su"}
    kuukaudet = {1: "Tam", 2: "Hel", 3: "Maa", 4: "Huh", 5: "Tou", 6: "Kes", 7: "Hei", 8: "Elo",
              9: "Syy", 10: "Lok", 11: "Mar", 12: "Jou"}
    #.format(paivat[viikonpva]), format(kuukaudet[kuukausi]),
    aika = "%s.%s.%s klo %s:%s:%s" % (kkpaiva, kuukausi, \
           vuosi, "{:02d}".format(tunti), "{:02d}".format(minuutti), "{:02d}".format(sekunti))
    return aika

def mqtt_palvelin_yhdista():
    aika = ratkaise_aika()
    if sta_if.isconnected():
        try:
            client.set_callback(seuraa_liiketta)
            client.connect()
            client.subscribe(AIHE_LIIKETUNNISTIN)

        except OSError as e:
            print("% s:  Ei voida yhdistaa! " % aika)
            time.sleep(10)
            restart_and_reconnect()
            return False
        return True
    else:
        print("%s: Yhteys on poikki! " % aika)
        restart_and_reconnect()
        return False

def laheta_pir(status):
    aika = ratkaise_aika()
    if sta_if.isconnected():
        try:
            client.connect()
            client.publish(AIHE_LIIKETUNNISTIN, str(status))  # 1 = liiketta, 0 = liike loppunut
        except OSError as e:
            print("% s:  Ei voida yhdistaa! " % aika)
            time.sleep(10)
            restart_and_reconnect()
            return False
        return True
    else:
        print("%s: Yhteys on poikki! " % aika)
        # client.disconnect()
        restart_and_reconnect()
        return False


def vilkuta_ledi(kertaa):
    ledipinni = machine.Pin(2, machine.Pin.OUT)
    for i in range(kertaa):
        ledipinni.on()
        utime.sleep_ms(100)
        ledipinni.off()
        utime.sleep_ms(100)

def restart_and_reconnect():
    aika = ratkaise_aika()
    print('%s: Ongelmia. Boottaillaan 5s kuluttua.' % aika)
    vilkuta_ledi(10)
    time.sleep(5)
    machine.reset()
    # resetoidaan


def keskeytyksen_seuranta(pin):
  global liike
  liike = True
  global keskeytys_pin
  keskeytys_pin = pin


def seuraa_liiketta():
    global liike
    # alustus
    pir.irq(trigger=Pin.IRQ_RISING, handler=keskeytyksen_seuranta)
    mqtt_palvelin_yhdista()
    while True:
        if liike:
            aika = ratkaise_aika()
            print('%s Liiketta havaittu! Keskeytysosoite: %s' %(aika, keskeytys_pin))
            # arvo 1 tarkoittaa liiketta
            laheta_pir(1)
            vilkuta_ledi(10)
            # odotetaan
            sleep(PIR_LIIKE_LOPPUAIKA)
            aika = ratkaise_aika()
            print('%s Liike loppunut!' %aika)
            # arvo 0 tarkoittaa liike loppunut
            laheta_pir(0)
            vilkuta_ledi(1)
            liike = False

if __name__ == "__main__":
    seuraa_liiketta()
