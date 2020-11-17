#!/usr/bin/env python3
"""
 Scripti sytyttää ulkovalot tunniksi kanalan ulkoluukun sulkeutumisen jälkeen ja tämän jälkeen aktivoi valot
 liiketunnistimelta tulleen liiketiedon perusteella.

 1.11.2020: Jari Hiltunen
 16.11.2020: Korjattu liikkeentunnistus ja lisätty loggausta

"""

import logging
import time
import datetime
from dateutil import tz
import signal
import sys
import os
from suntime import Sun
import paho.mqtt.client as mqtt  # mqtt kirjasto

from parametrit import LUUKKUAIHE, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, MQTTSERVERIPORTTI, \
    LATITUDI, LONGITUDI, RELE3_MQTTAIHE_3, VALO_ENNAKKO_AIKA_POHJOINEN_1, \
    LIIKE_PAALLAPITO_AIKA_ETELA_1, LIIKETUNNISTIN_POHJOINEN_AIHE, VALOT_POIS_KLO_POHJOINEN_1

''' Globaalit päivämäärämuuttujat'''
aikavyohyke = tz.tzlocal()
aika_nyt = datetime.datetime.now().astimezone(aikavyohyke)
auringon_lasku_tanaan = datetime.datetime.now().astimezone(aikavyohyke)
auringon_lasku_huomenna = datetime.datetime.now().astimezone(aikavyohyke)
auringon_nousu_huomenna = datetime.datetime.now().astimezone(aikavyohyke)
auringon_nousu_tanaan = datetime.datetime.now().astimezone(aikavyohyke)
luukku_suljettu_aika = datetime.datetime.now().astimezone(aikavyohyke)


''' Globaalit muuttujat ja liipaisimet '''
aurinko_laskenut = False
aurinko_noussut = True
ohjausobjektit = []
luukku_auki = False


""" Objektien luonti """
aurinko = Sun(LATITUDI, LONGITUDI)
''' Yhteysobjektit '''
mqttvalot = mqtt.Client("ulkovalojenohjaus")
mqttvalot.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari


def virhe_loggeri(login_formaatti='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                  login_nimi='', logitiedosto_infoille='/home/pi/Kanala/info/ohjausulkovalo-info.log',
                  logitiedosto_virheille='/home/pi/Kanala/virheet/ohjausulkovalo-virhe.log'):
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
    loggeri.info("Prosessi %s terminoitu klo %s." % (os.getpid(), aika_nyt))
    sys.exit()


def yhdista_mqtt(client, userdata, flags, rc):
    if client.is_connected() is False:
        try:
            client.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, 60, bind_address="")  # yhdista mqtt-brokeriin
        except OSError as e:
            loggeri.error("MQTT-palvelinongelma %s", e)
            raise Exception("MQTT-palvelinongelma! %s" % e)
        print("Yhdistetty statuksella: " + str(rc))
        loggeri.info("Yhdistetty statuksella: " + str(rc))
    client.subscribe(LUUKKUAIHE)  # tilaa aihe luukun statukselle
    """ Tilataan aiheet mqtt-palvelimelle. [0] ohjausobjekteissa tarkoittaa liikeanturia """
    # mqttvalot.subscribe("$SYS/#")
    for z in range(len(ohjausobjektit)):
        client.subscribe(ohjausobjektit[z][0].liikeaihe)


def pura_yhteys_mqtt():
    mqttvalot.loop_stop()
    try:
        mqttvalot.disconnect()
    except OSError as e:
        loggeri.error("MQTT-palvelinongelma! %s", e)
        raise Exception("MQTT-palvelinongelma! %s" % e)


class Valojenohjaus:
    """ Konstruktorissa muodostetaan valoja ohjaava objekti, jota päivitetään loopissa """
    global aika_nyt

    def __init__(self, ohjausaihe, aamu_paalle_aika, ilta_pois_aika):  # konstruktori
        """
       1. IN: aihe string
       2. IN: aamu_paalle_aika on aika joka pidetään valoja päällä ennen ennakko_aika loppumista mikäli
          aurinko laskenut (TT:MM) esimerkiksi 08:00 saakka
       3. IN: ilta_pois_aika tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM)
          esimerkiksi 21:00

          Kutsumalla muuta_valo_paalle_aika (2) tai muuta_valo_pois_aika (3) voit muuttaa aikoja.
       """

        if (ohjausaihe is None) or (aamu_paalle_aika is None) or (ilta_pois_aika is None):
            raise Exception("Aihe tai aika puuttuu!")
        self.ohjausaihe = ohjausaihe
        """ 2. paalle_aika tarkoittaa aikaa mihin saakka pidetään valoja päällä ellei aurinko ole noussut """
        self.aamu_paalla_tunnit, self.aamu_paalla_minuutit = map(int, aamu_paalle_aika.split(':'))
        """ 3. valot_pois tarkoittaa aikaa jolloin valot tulee viimeistään sammuttaa päivänpituudesta riippumatta """
        self.ilta_pois_tunnit, self.ilta_pois_minuutit = map(int, ilta_pois_aika.split(':'))

        # Objektin luontihekten aika
        self.aamu_paalle_aika = aika_nyt.replace(hour=self.aamu_paalla_tunnit, minute=self.aamu_paalla_minuutit)
        self.ilta_pois_aika = aika_nyt.replace(hour=self.ilta_pois_tunnit, minute=self.ilta_pois_minuutit)

        self.valot_paalla = False
        self.pitoajalla = False
        self.liikeyllapitoajalla = False

        ''' Päivämäärämuuttujien alustus'''
        self.valot_ohjattu_pois = None
        self.valot_ohjattu_paalle = None

    def __del__(self):
        """ Konstruktorin poistoa varten, joko roskankeruurutiinin gc tai del-komennon vuoksi """

    def __str__(self):
        """ Palauttaa ohjausaiheen """
        return self.ohjausaihe

    def __repr__(self):
        """ Palauttaa luokan nimen, ohjausaiheen ja statukset """
        return '[%s: %s, %s, %s, %s]' % (self.__class__.__name__, self.ohjausaihe,
                                         self.valot_paalla, self.pitoajalla, self.liikeyllapitoajalla)

    def uusi_valo_paalle_aika(self):
        #  Aika ennen auringonnousua
        self.aamu_paalle_aika = aika_nyt.replace(hour=self.aamu_paalla_tunnit, minute=self.aamu_paalla_minuutit)
        return self.aamu_paalle_aika

    def uusi_valo_pois_aika(self):
        #  Aika illalla jolloin valot sammutetaan
        self.ilta_pois_aika = aika_nyt.replace(hour=self.ilta_pois_tunnit, minute=self.ilta_pois_minuutit)
        return self.ilta_pois_aika

    def muuta_valo_pois_aika(self, tunnit, minuutit):
        #  IN: tunnit ja minuutit int
        if (tunnit < 0) or (tunnit > 24) or (minuutit < 0) or (minuutit > 59):
            print("Valojen aikamuutoksessa väärä arvo!")
            return False
        else:
            self.ilta_pois_aika = aika_nyt.replace(hour=tunnit, minute=minuutit)
            return self.ilta_pois_aika

    def muuta_valo_paalle_aika(self, tunnit, minuutit):
        #  IN: tunnit ja minuutit int
        if (tunnit < 0) or (tunnit > 24) or (minuutit < 0) or (minuutit > 59):
            print("Valojen aikamuutoksessa väärä arvo!")
            return False
        else:
            self.aamu_paalle_aika = aika_nyt.replace(hour=tunnit, minute=minuutit)
            return self.aamu_paalle_aika

    def valojen_ohjaus(self, status):
        """ IN: status on joko int 1 tai 0 riippuen siitä mitä releelle lähetetään """
        if mqttvalot.is_connected() is False:
            try:
                mqttvalot.loop_stop()
                mqttvalot.loop_start()
            except mqttvalot.is_connected() is False:
                raise Exception("Yhteys palvelimeen %s ei toimi!" % MQTTSERVERI)
        else:
            if (status < 0) or (status > 1):
                loggeri.error("%s Valojen ohjausarvon tulee olla 0 tai 1!" % self.__class__.__name__)
                raise Exception("Valojen ohjausarvon tulee olla 0 tai 1!")
            elif status == 0:
                self.valot_paalla = False
            elif status == 1:
                self.valot_paalla = True
            try:
                mqttvalot.publish(self.ohjausaihe, payload=status, qos=1, retain=True)  # Huom! QoS = 1
            except AttributeError:
                pass
            except OSError as e:
                loggeri.error("%s Virhe %s!" % (self.__class__.__name__, e))
                raise Exception("Virhetila %s", e)


class Liikeohjaus:
    """ Konstruktorissa muodostetaan liikettä havainnoivat objektit """

    def __init__(self, liikeaihe, paallapitoaika):
        """ IN: aihe (str) ja päälläpitoaika sekunteja (int) """
        if (liikeaihe is None) or (paallapitoaika is None):
            raise Exception("Aihe tai päälläpitoaika puuttuu!")
        self.liikeaihe = liikeaihe
        self.paallapitoaika = paallapitoaika
        self.liiketta_havaittu = False
        self.liiketta_havaittu_klo = datetime.datetime.now().astimezone(aikavyohyke)
        self.liike_loppunut_klo = datetime.datetime.now().astimezone(aikavyohyke)
        self.loppumisaika_delta = 0

    def __del__(self):
        """ Konstruktorin poistoa varten, joko roskankeruurutiinin gc tai del-komennon vuoksi """

    def __str__(self):
        """ Palauttaa liikeaiheen """
        return self.liikeaihe

    def __repr__(self):
        """ Palauttaa luokan nimen, liikeaiheen ja statukset """
        return '[%s: %s, %s, %s, %s]' % (self.__class__.__name__, self.liikeaihe,
                                         self.liiketta_havaittu, self.liiketta_havaittu_klo,
                                         self.liike_loppunut_klo)

    def muuta_paallapito_aika(self, aika):
        """ Muuttaa paallapitoaikaa. IN: int sekunteja """
        self.paallapitoaika = aika


def mqtt_viesti_vastaanotettu(client, userdata, message):
    global ohjausobjektit
    global luukku_suljettu_aika, luukku_auki
    """ Havaitaan aika jolloin luukku on suljettu tai avattu """
    if message.topic == LUUKKUAIHE:
        viesti = int(message.payload)
        if viesti == 0:
            print("Luukku suljettu klo %s" % datetime.datetime.now().astimezone(aikavyohyke))
            luukku_suljettu_aika = datetime.datetime.now().astimezone(aikavyohyke)
            luukku_auki = False
        elif viesti == 1:
            print("Luukku avattu klo %s" % datetime.datetime.now().astimezone(aikavyohyke))
            luukku_auki = True
    else:
        """ Selvitetään mille liikeobjektille viesti kuuluu [0] = liike, [1] = ohjaus """
        # print("Viesti %s : %s" % (message.topic, message.payload))
        for z in range(len(ohjausobjektit)):
            if message.topic == ohjausobjektit[z][0].liikeaihe:
                viesti = int(message.payload)
                if viesti == 1:
                    ohjausobjektit[z][0].liiketta_havaittu = True
                    ohjausobjektit[z][0].liiketta_havaittu_klo = datetime.datetime.now().astimezone(aikavyohyke)
                else:
                    ohjausobjektit[z][0].liiketta_havaittu = False
                    ohjausobjektit[z][0].liike_loppunut_klo = datetime.datetime.now().astimezone(aikavyohyke)
                    if ohjausobjektit[z][0].liiketta_havaittu_klo is not None:
                        ohjausobjektit[z][0].loppumisaika_delta = \
                            ohjausobjektit[z][0].liike_loppunut_klo - ohjausobjektit[z][0].liiketta_havaittu_klo
                    else:
                        ohjausobjektit[z][0].loppumisaika_delta = 0


def laske_auringon_lasku():
    # Out: statukset
    global aurinko_noussut, aurinko_laskenut, aika_nyt, auringon_lasku_tanaan, auringon_lasku_huomenna, \
        auringon_nousu_huomenna, auringon_nousu_tanaan
    ''' Huom! Palauttaa UTC-ajan ilman astitimezonea'''
    auringon_nousu_tanaan = aurinko.get_sunrise_time().astimezone(aikavyohyke)
    ''' Lisätään auringon laskuu 30 minuuttia jotta ehtii tulla pimeää '''
    auringon_lasku_tanaan = aurinko.get_sunset_time().astimezone(aikavyohyke) + datetime.timedelta(minutes=30)
    auringon_nousu_huomenna = aurinko.get_sunrise_time().astimezone(aikavyohyke) + datetime.timedelta(days=1)

    ''' Mikäli käytät asetuksissa utc-aikaa, käytä alla olevaa riviä 
    ja muista vaihtaa datetime-kutusissa tzInfo=None'''
    aika_nyt = datetime.datetime.now().astimezone(aikavyohyke)

    ''' Testaamista varten

    global testitunnit, testiminuutit
    testiminuutit = testiminuutit + 1
    if testiminuutit >= 60:
        testiminuutit = 0
        testitunnit = testitunnit + 1
        if testitunnit >= 24:
            testitunnit = 0
    aika_nyt = aika_nyt.replace(hour=testitunnit, minute=testiminuutit)
    print("A: %s - AL: %s - AN: %s" % (aika_nyt.time(), auringon_lasku_tanaan.time(), auringon_nousu_tanaan.time()))

    '''

    ''' Auringon nousu tai laskulogiikka '''

    if (aika_nyt >= auringon_lasku_tanaan) and (aika_nyt < auringon_nousu_huomenna):
        aurinko_noussut = False
        aurinko_laskenut = True
    elif aika_nyt < auringon_nousu_tanaan:
        aurinko_noussut = False
        aurinko_laskenut = True
    else:
        aurinko_noussut = True
        aurinko_laskenut = False


def liiketunnistus(liikeobjekti, valoobjekti):
    """ IN: liikeobjektin ja valo-objektin nimet"""
    try:
        liikeobjekti
    except NameError:
        loggeri.error("%s objektia ei löydy!" % liikeobjekti)
        raise Exception("Liikeobjektin nimeä ei löydy!")
    else:
        try:
            valoobjekti
        except NameError:
            loggeri.error("%s objektia ei löydy!" % valoobjekti)
            raise Exception("Valo-objektin nimeä ei löydy!")

    liikeobjekti.loppumisaika_delta = (datetime.datetime.now().astimezone(aikavyohyke)
                                       - liikeobjekti.liike_loppunut_klo).total_seconds()

    ''' Liiketunnistuksen mukaan valojen sytytys ja sammutus ajan ylityttyä '''
    if (aurinko_laskenut is True) and (valoobjekti.valot_paalla is False) and (liikeobjekti.liiketta_havaittu is True):
        valoobjekti.valojen_ohjaus(1)
        valoobjekti.liikeyllapitoajalla = True
        valoobjekti.valot_ohjattu_paalle = datetime.datetime.now().astimezone(aikavyohyke)
        loggeri.info("%s: valot sytytetty liiketunnistunnistuksen %s vuoksi klo %s"
                     % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, valoobjekti.valot_ohjattu_paalle))
        print("%s: valot sytytetty liiketunnistunnistuksen %s vuoksi klo %s"
              % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, valoobjekti.valot_ohjattu_paalle))

    if (aurinko_laskenut is True) and (valoobjekti.valot_paalla is True) and (liikeobjekti.liiketta_havaittu is False) \
            and (liikeobjekti.loppumisaika_delta > liikeobjekti.paallapitoaika) and (valoobjekti.pitoajalla is False):
        valoobjekti.valojen_ohjaus(0)
        loggeri.info("%s: Valot sammutettu liikkeen %s loppumisen vuoksi. Liikedelta: %s"
                     % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, liikeobjekti.loppumisaika_delta))
        print("%s: Valot sammutettu liikkeen %s loppumisen vuoksi. Liikedelta: %s"
              % (valoobjekti.ohjausaihe, liikeobjekti.liikeaihe, liikeobjekti.loppumisaika_delta))
        valoobjekti.liikeyllapitoajalla = False
        valoobjekti.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)


def ohjausluuppi():
    global ohjausobjektit
    global aurinko_noussut
    global luukku_suljettu_aika

    loggeri.info('PID %s. Sovellus käynnistetty %s' % (os.getpid(), datetime.datetime.now().astimezone(aikavyohyke)))

    """ Yhteys on kaikille valo-objekteille sama """
    mqttvalot.on_connect = yhdista_mqtt  # mita tehdaan kun yhdistetaan brokeriin
    mqttvalot.on_disconnect = pura_yhteys_mqtt
    mqttvalot.on_message = mqtt_viesti_vastaanotettu  # maarita mita tehdaan kun viesti saapuu

    """ Valojenohjausobjektit """
    # OUT: ohjausaihe, paalle_aika, pois_aika
    ulkovalot = Valojenohjaus(RELE3_MQTTAIHE_3, VALO_ENNAKKO_AIKA_POHJOINEN_1, VALOT_POIS_KLO_POHJOINEN_1)

    """ Liiketunnistimet tilaavat automaattisesti aiheensa """
    # OUT: aihe, paallapitoaika
    ulko_pir = Liikeohjaus(LIIKETUNNISTIN_POHJOINEN_AIHE, LIIKE_PAALLAPITO_AIKA_ETELA_1)

    """ Valo-objektit ja liikeobjektit paritettuna, eli mikä liikeobjekti ohjaa mitäkin valo-objektia """
    ohjausobjektit = [[ulko_pir, ulkovalot]]

    """ Käynnistetään mqtt-pollaus"""
    mqttvalot.connect_async(MQTTSERVERI, MQTTSERVERIPORTTI, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttvalot.loop_start()

    """ Suoritetaan looppia kunnes toiminta katkaistaan"""

    while True:

        try:
            laske_auringon_lasku()
            if (aurinko_laskenut is True) and (luukku_auki is False) and \
                    (datetime.datetime.now().astimezone(aikavyohyke) - luukku_suljettu_aika) < \
                    datetime.timedelta(minutes=60) and (ulkovalot.valot_paalla is False):
                """" Luukun sulkemisesta alle 60 minuuttia. Sytytetään valot """
                ulkovalot.valojen_ohjaus(1)
                ulkovalot.pitoajalla = True
                ulkovalot.valot_ohjattu_paalle = datetime.datetime.now().astimezone(aikavyohyke)
                loggeri.info("%s: Valot ohjattu päälle", ulkovalot.valot_ohjattu_paalle)
            elif (aurinko_laskenut is True) and (luukku_auki is False) and \
                    (datetime.datetime.now().astimezone(aikavyohyke) - luukku_suljettu_aika) >= \
                    datetime.timedelta(minutes=60) and (ulkovalot.valot_paalla is True) and \
                    (ulkovalot.liikeyllapitoajalla is False):
                """" Luukun sulkemisesta yli 60 minuuttia. Sammutetaan valot """
                ulkovalot.valojen_ohjaus(0)
                ulkovalot.pitoajalla = False
                ulkovalot.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)
                loggeri.info("%s: Valot ohjattu pois", ulkovalot.valot_ohjattu_pois)
            elif (aurinko_laskenut is True) and (luukku_auki is False) and \
                    (datetime.datetime.now().astimezone(aikavyohyke) - luukku_suljettu_aika) >= \
                    datetime.timedelta(minutes=60) and (ulkovalot.valot_paalla is False):
                """" Tarkkaillaan liikettä """
                for z in range(len(ohjausobjektit)):
                    liiketunnistus(ohjausobjektit[z][0], ohjausobjektit[z][1])
            elif (aurinko_laskenut is False) and (ulkovalot.valot_paalla is True):
                """ Sammutetaan valot, aurinko noussut """
                ulkovalot.valojen_ohjaus(0)
                ulkovalot.pitoajalla = False
                ulkovalot.liikeyllapitoajalla = False
                ulkovalot.valot_ohjattu_pois = datetime.datetime.now().astimezone(aikavyohyke)
                loggeri.info("%s: Aurinko noussut. Valot ohjattu pois", ulkovalot.valot_ohjattu_pois)

        except KeyboardInterrupt:
            raise

        time.sleep(0.1)  # suoritetaan 0.1s valein


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminoi_prosessi)
    ohjausluuppi()
