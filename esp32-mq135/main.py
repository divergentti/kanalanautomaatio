""" MQ135-sensorille:
    ESP32:n ADC-pinnin V on 0.0 - 1.0 V ja kaikki sen yli palauttaa 4095!
    Tee vastuksilla splitteri, esimerkiksi 5V:sta R1=40K ja R2=10K josta
    40K menee 5V ja 10K maihin. Tasta valista otat lahdon ADC:lle.

    Sensorin datasheetilta:
    - Rs 30 KOhm - 200 KOhm
    - RL = 20 KOhm
    - Ro = 100 ppm NH3 puhtaassa ilmassa
    - O2 standardi 21 %, Temp 20C, Rh 65 %
    - Rh vaikutus Rh ja lampo: Rs/Ro = 1 (20C/33 % Rh), Rs/Ro = 1.7 (-10C/33 % Rh)
    - Rh 33 % -> 85 % vaikutus Rs/Ro = 0.1
    - Scopet NH3 = 10 - 300 ppm
    - Bentseeni 10 - 1000 ppm
    - Alkoholi 10 - 300 ppm
    Lämpötila ja kosteus tuodaan mqtt-palvelimelta
"""
import math  # tarvitaan laskennassa
import time
import utime
import machine # tuodaan koko kirjasto
from machine import Pin
from machine import ADC
from umqttsimple import MQTTClient
import network

# Raspberry WiFi on huono ja lisaksi raspin pitaa pingata ESP32 jotta yhteys toimii!
sta_if = network.WLAN(network.STA_IF)

# tuodaan parametrit tiedostosta parametrit.py
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
    MQTT_SALASANA, SISA_LAMPO, SISA_KOSTEUS, SISA_PPM, MQ135_PINNI

client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

lampo = 0  # oletukset
kosteus = 0  # oletukset

class MQ135(object):
    """
    Source rubfi: https://raw.githubusercontent.com/rubfi/MQ135/master/mq135.py

    Modified for the ESP32 by Divergentti / Jari Hiltunen

    Micropython library for dealing with MQ135 gas sensor
    Based on Arduino Library developed by G.Krocker (Mad Frog Labs)
    and the corrections from balk77 and ViliusKraujutis

    More info:
        https://hackaday.io/project/3475-sniffing-trinket/log/12363-mq135-arduino-library
        https://github.com/ViliusKraujutis/MQ135
        https://github.com/balk77/MQ135
    """
    """ Class for dealing with MQ13 Gas Sensors """
    # The load resistance on the board
    RLOAD = 10.0
    # Calibration resistance at atmospheric CO2 level
    RZERO = 76.63
    # Parameters for calculating ppm of CO2 from sensor resistance
    PARA = 116.6020682
    PARB = 2.769034857

    # Parameters to model temperature and humidity dependence
    CORA = 0.00035
    CORB = 0.02718
    CORC = 1.39538
    CORD = 0.0018
    CORE = -0.003333333
    CORF = -0.001923077
    CORG = 1.130128205

    # Atmospheric CO2 level for calibration purposes
    ATMOCO2 = 397.13

    def __init__(self, pin):
        self.pin = pin

    def get_correction_factor(self, temperature, humidity):
        """Calculates the correction factor for ambient air temperature and relative humidity

        Based on the linearization of the temperature dependency curve
        under and above 20 degrees Celsius, asuming a linear dependency on humidity,
        provided by Balk77 https://github.com/GeorgK/MQ135/pull/6/files
        """

        if temperature < 20:
            return self.CORA * temperature * temperature - self.CORB * temperature + self.CORC - (humidity - 33.) * self.CORD

        return self.CORE * temperature + self.CORF * humidity + self.CORG

    def get_resistance(self):
        """Returns the resistance of the sensor in kOhms // -1 if not value got in pin"""
        adc = ADC(self.pin)
        value = adc.read()
        if value == 0:
            return -1

        return (4095./value - 1.) * self.RLOAD  # ESP32 maksimi, ESP8266:lle arvo on 1023

    def get_corrected_resistance(self, temperature, humidity):
        """Gets the resistance of the sensor corrected for temperature/humidity"""
        return self.get_resistance()/ self.get_correction_factor(temperature, humidity)

    def get_ppm(self):
        """Returns the ppm of CO2 sensed (assuming only CO2 in the air)"""
        return self.PARA * math.pow((self.get_resistance()/ self.RZERO), -self.PARB)

    def get_corrected_ppm(self, temperature, humidity):
        """Returns the ppm of CO2 sensed (assuming only CO2 in the air)
        corrected for temperature/humidity"""
        return self.PARA * math.pow((self.get_corrected_resistance(temperature, humidity)/ self.RZERO), -self.PARB)

    def get_rzero(self):
        """Returns the resistance RZero of the sensor (in kOhms) for calibratioin purposes"""
        return self.get_resistance() * math.pow((self.ATMOCO2/self.PARA), (1./self.PARB))

    def get_corrected_rzero(self, temperature, humidity):
        """Returns the resistance RZero of the sensor (in kOhms) for calibration purposes
        corrected for temperature/humidity"""
        return self.get_corrected_resistance(temperature, humidity) * math.pow((self.ATMOCO2/self.PARA), (1./self.PARB))

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
            client.set_callback(palauta_lampo_ja_rh)
            client.connect()
            client.subscribe(SISA_LAMPO)  # lampotila C
            client.subscribe(SISA_KOSTEUS)  # suhteellinen kosteus %
        except OSError as e:
            print("% s:  Ei voida yhdistaa! " % aika)
            client.disconnect()
            time.sleep(10)
            restart_and_reconnect()
            return False
        return True
    else:
        print("%s: Yhteys on poikki! " % aika)
        # client.disconnect()
        restart_and_reconnect()
        return False

def palauta_lampo_ja_rh(topic, msg):
    global lampo, kosteus
    if topic == SISA_LAMPO:
        lampo = msg  # uusi lampotila
    if topic == SISA_KOSTEUS:
        kosteus = msg  # uusi kosteus
    return

def laheta_ppm_mqtt(ppm):
    aika = ratkaise_aika()
    if sta_if.isconnected():
        try:
            client.connect()
            client.publish(SISA_PPM, str(ppm))  # julkaistaan ppm arvo
        except OSError as e:
            print("% s:  Ei voida yhdistaa! " % aika)
            client.disconnect()
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


def palauta_PPM():
    global lampo, kosteus
    """Lukee viimeisimmän temp- ja Rh arvot mtqq:lta ja luo mq135-sensoriobjektin"""
    # setup
    mqtt_palvelin_yhdista()   # lampo ja kosteus pitaisi olla muuttunut oletuksesta
    print("Odotellaan ensimmaista arvoa mqtt:lle...")
    client.wait_msg()
    if (lampo == 0) or (kosteus == 0):
        client.wait_msg()  # kokeile lukua uudelleen
        if (lampo == 0) or (kosteus == 0):
            print("Ei onnistu. Lampo %s, kosteus %s" %(lampo, kosteus))
            raise OSError
    print ("Lampo %s, kosteus %s" %(lampo, kosteus))
    temperature = float(lampo)
    humidity = float(kosteus)
    mq135 = MQ135(Pin(MQ135_PINNI))  # objektin luonti, analogi PIN 0 ESP32 ADC0
    ppm_lista = []  # keskiarvon laskentaa varten
    print("Luetaan ensimmaiset 60 arvoa listalle kerran sekunnissa ... odota")
    # looppi
    while True:
        try:
            #  rzero = mq135.get_rzero()
            #  corrected_rzero = mq135.get_corrected_rzero(temperature, humidity)
            #  resistance = mq135.get_resistance()
            #  ppm = mq135.get_ppm()
            # corrected_ppm = mq135.get_corrected_ppm(temperature, humidity)
            ppm_lista.append(mq135.get_corrected_ppm(temperature, humidity))
            vilkuta_ledi(1)
        except ValueError:
            pass
        #print("MQ135 RZero: " + str(rzero) + "\t Corrected RZero: " + str(corrected_rzero) +
        #        "\t Resistance: " + str(resistance) + "\t PPM: " + str(ppm) +
        #        "\t Corrected PPM: " + str(corrected_ppm) + "ppm")


        if len(ppm_lista) == 60:
            # lasketaan minuutin keskiarvo PPM:lle
            keskiarvo = sum(ppm_lista) / len(ppm_lista)
            print("Tallennettava keskiarvo on: %s " %keskiarvo)
            # julkaistaan keskiarvo mqtt
            laheta_ppm_mqtt(keskiarvo)
            # luetaan uusi lampotila ja kosteusarvo
            client.check_msg() # tarkisetaan uusia arvoja
            client.check_msg()  # tarkisetaan uusia arvoja
            print ("Uusi lampo %s ja kosteus %s" %(lampo, kosteus))
            temperature = float(lampo)
            humidity = float(kosteus)
            vilkuta_ledi(2)
            ppm_lista.clear() # nollataan lista
            print ("Luetaan seuraavat 60 arvoa listalle... odota")
        time.sleep(1)  # lukuvali 1s.

if __name__ == "__main__":
    palauta_PPM()
