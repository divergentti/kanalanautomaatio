#!/usr/bin/env python3
"""
Valojen varsinainen ohjaus tapahtuu mqtt-viesteillä, joita voivat lähettää esimerkiksi lähestymisanturit,
kännykän sovellus tai jokin muu IoT-laite.

Ulkotiloissa valoja on turha sytyttää, jos valoisuus riittää muutenkin. Tieto valoisuudesta saadaan mqtt-kanaviin
valoantureilla, mutta lisätieto auringon nousu- ja laskuajoista voi olla myös tarpeen.

Tämä scripti laskee auringon nousu- ja laskuajat ja lähettää mqtt-komennon valojen päälle kytkemiseen tai sammuttamiseen.
Lisäksi tämä scripti kuuntelee tuleeko liikesensoreilta tietoa liikkeestä ja laittaa valot päälle mikäli
aurinko on jo laskenut. LIIKE_PAALLAPITO_AIKA määrittää miten pitkään valoja pidetään päällä liikkeen havaitsemisen
jälkeen.

Muuttujina valojen päälläolon suhteen ovat VALOT_POIS_KLO ja VALO_ENNAKKO_AIKA.
- VALOT_POIS tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM)
- VALO_ENNAKKO_AIKA tarkoittaa aikaa jolloin valot sytytetään ennen auringonnousua (string TT:MM).

Ajat ovat paikallisaikaa (parametrit.py-tiedostossa).

Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

3.9.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt # mqtt kirjasto
import time
# import syslog  # Syslogiin kirjoittamista varten
import datetime
from dateutil import tz
import logging
from suntime import Sun, SunTimeException
from parametrit import LATITUDI, LONGITUDI, MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALOT_POIS_KLO, \
    VALO_ENNAKKO_AIKA, LIIKETUNNISTIN_ETELA_1, LIIKE_PAALLAPITO_AIKA

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

''' Globaalit muuttujat ja liipaisimet '''
valot_paalla = False
aurinko_laskenut = False


''' Globaalit päivämäärämuuttujat'''
liiketta_havaittu_klo = datetime.datetime.strptime('01/01/02 01:01:01', '%m/%d/%y %H:%M:%S')
liike_loppunut_klo = datetime.datetime.strptime('01/01/02 01:01:01', '%m/%d/%y %H:%M:%S')
liiketta_havaittu = False

''' Laskentaobjektit '''
aurinko = Sun(LATITUDI, LONGITUDI)

''' mqtt-objektit'''
mqttasiakas = mqtt.Client("valojenohjaus-laskettu")  # mqtt objektin luominen, tulla olla uniikki nimi
mqttliiketieto = mqtt.Client("valojenohjaus-liiketieto")  # mqtt objektin luominen, tulla olla uniikki nimi

''' 
Longitudin ja latitudin saat syöttämällä osoitteen esimerkiksi Google Mapsiin.
'''

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2

def mqttyhdistaliike(mqttliiketieto, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttliiketieto.subscribe(LIIKETUNNISTIN_ETELA_1)  # tilaa aihe liikkeelle

def mqttliike_pura_yhteys(mqttliiketieto, userdata,rc=0):
    logging.debug("Yhteys purettu: "+str(rc))
    mqttliiketieto.loop_stop()


def valojen_ohjaus(status):
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    ''' Status on joko 1 tai 0 riippuen siitä mitä releelle lähetetään'''
    """ Tassa kaytetaan salaamatonta porttia ilman TLS:aa, vaihda tarvittaessa """
    try:
        ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
        mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=status, retain=True)
    except OSError:
        print("Virhe %d" % OSError)
        logging.error('Valonohjaus OS-virhe %s' % OSError)
    return

def mqttviestiliike(mqttliiketieto, userdata, message):
    global liiketta_havaittu_klo
    global liike_loppunut_klo
    global liiketta_havaittu

    """ Tarkastellaan josko liiketunnistimelta olisi tullut viestiä """

    viesti = int(message.payload)
    if (viesti < 0) or (viesti > 1):
        print("Virheellinen arvo!")
        logging.error("valojenohjaus.py - Virheellinen arvo kutsussa!")
        return False

    if (viesti == 1):
        liiketta_havaittu = True
        liiketta_havaittu_klo = datetime.datetime.now()
        return
    else:
        liiketta_havaittu = False
        liike_loppunut_klo = datetime.datetime.now()
        return


def ohjausluuppi():
    global aurinko_laskenut
    global valot_paalla
    global liiketta_havaittu_klo
    global liike_loppunut_klo
    global liiketta_havaittu

    ''' Toistetaan yhteydenotto, sillä yhteys on voinut katketa keepalive-asetuksen mukaisesti '''
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttliiketieto.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttliiketieto.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttliiketieto.on_connect = mqttyhdistaliike  # mita tehdaan kun yhdistetaan brokeriin
    mqttliiketieto.on_disconnect = mqttliike_pura_yhteys # mita tehdaan kun yhteys lopetetaan
    mqttliiketieto.on_message = mqttviestiliike  # maarita mita tehdaan kun viesti saapuu

    ''' Päivämäärämuuttujat'''
    valot_ohjattu_pois = datetime.datetime.strptime('02/02/18 02:02:02', '%m/%d/%y %H:%M:%S')
    valot_ohjattu_paalle = datetime.datetime.strptime('01/01/18 01:01:01', '%m/%d/%y %H:%M:%S')
    aikavyohyke = tz.tzlocal()

    ''' Lähetettään komento valot pois varmuuden vuoksi'''
    valojen_ohjaus(0)

    ''' Testaamista varten, iteraattori esimerkiksi tunneille
    x = 18
    '''


    """ Suoritetaan looppia kunnes toiminta katkaistaan"""
    while True:
        try:
            ''' Looppia tulee päivittää jotta tieto kanavasta saadaa luettua '''
            mqttliiketieto.loop_start()

            ''' Palauttaa UTC-ajan ilman astitimezonea'''
            auringon_nousu = aurinko.get_sunrise_time().astimezone(aikavyohyke)
            auringon_lasku = aurinko.get_sunset_time().astimezone(aikavyohyke)

            ''' Mikäli käytät asetuksissa utc-aikaa, käytä alla olevaa riviä ja muista vaihtaa
                datetime-kutusissa tzInfo=None'''
            aika_nyt= datetime.datetime.now()

            ''' Testaamista varten 
            x = x + 1
            if x >= 24:
                x = 0
            aika_nyt = aika_nyt.replace(hour=x, minute=59)
            print (aika_nyt)
            '''

            ''' Pythonin datetime naiven ja awaren vuoksi puretaan päivä ja aika osiin '''
            nousu_paiva = auringon_nousu.date()
            laskuaika_arvo = (auringon_lasku.time().hour * 60) + auringon_lasku.time().minute
            aika_nyt_paiva = aika_nyt.date()
            aika_nyt_arvo = (aika_nyt.hour * 60) + aika_nyt.minute

            ''' Kelloaika ennen auringonnousua jolloin valot tulisi laittaa päälle '''
            ennakko_tunnit, ennakko_minuutit = map(int, VALO_ENNAKKO_AIKA.split(':'))
            ennakko_arvo = (ennakko_tunnit * 60) + ennakko_minuutit

            ''' Valot_pois tarkoittaa aikaa jolloin valot tulee viimeistään sammuttaa päivänpituudesta riippumatta '''
            pois_tunnit, pois_minuutit = map(int, VALOT_POIS_KLO.split(':'))
            pois_arvo = (pois_tunnit * 60) + pois_minuutit

            ''' Auringon nousu tai laskulogiikka '''
            if (nousu_paiva == aika_nyt_paiva) and (laskuaika_arvo > aika_nyt_arvo):
                aurinko_noussut = True
                aurinko_laskenut = False
            else:
                aurinko_noussut = False
                aurinko_laskenut = True

            ''' Valojen sytytys ja sammutuslogiikka'''

            ''' Jos aurinko on laskenut, sytytetään valot, jos ei olla yli sammutusajan'''
            if (aurinko_laskenut == True) and (valot_paalla == False) and (aika_nyt_arvo < pois_arvo):
                valojen_ohjaus(1)
                valot_paalla = True
                valot_ohjattu_paalle = datetime.datetime.now()
                print("Aurinko laskenut. Valot sytytetty.")


            ''' Aurinko laskenut ja valot päällä, mutta sammutusaika saavutettu '''
            if (aurinko_laskenut == True) and (valot_paalla == True) and (aika_nyt_arvo >= pois_arvo):
                valojen_ohjaus(0)
                valot_paalla = False
                valot_ohjattu_pois = datetime.datetime.now()
                valot_olivat_paalla = valot_ohjattu_pois - valot_ohjattu_paalle
                print("Valot sammutettu. Valot olivat päällä %s" % valot_olivat_paalla)

            ''' Tarkistetaan ollaanko ennakkoajalla, eli mihin saakka valojen tulisi olla päällä '''

            if (valot_paalla == False) and (aurinko_laskenut == True) and aika_nyt_arvo <= ennakko_arvo \
                and (valot_ohjattu_pois.date() != aika_nyt_paiva):
                valojen_ohjaus(1)
                valot_paalla = True
                valot_ohjattu_paalle = datetime.datetime.now()
                print("Valot sytytetty ennakkoajan mukaisesti")

            ''' Jos aurinko noussut, sammutetaan valot '''
            if (aurinko_noussut == True) and (valot_paalla == True):
                valojen_ohjaus(0)
                valot_paalla = False
                valot_ohjattu_pois = datetime.datetime.now()
                valot_olivat_paalla = valot_ohjattu_pois - valot_ohjattu_paalle
                print("Aurinko noussut. Valot sammutettu. Valot olivat päällä: %s" % valot_olivat_paalla)

            loppumisaika_delta = (datetime.datetime.now() - liike_loppunut_klo).total_seconds()

            ''' Liiketunnistuksen mukaan valojen sytytys ja sammutus ajan ylityttyä '''
            if (aurinko_laskenut == True) and (valot_paalla == False) and (liiketta_havaittu == True):
                valojen_ohjaus(1)
                valot_paalla = True
                valot_ohjattu_paalle = datetime.datetime.now()
                print("Valot sytytetty liiketunnistunnistuksen vuoksi")
            elif (aurinko_laskenut == True) and (valot_paalla == True) and (liiketta_havaittu == False) and \
                    (loppumisaika_delta > LIIKE_PAALLAPITO_AIKA):
                valojen_ohjaus(0)
                valot_paalla = False
                valot_ohjattu_pois = datetime.datetime.now()

            time.sleep(0.1) # suoritetaan 0.1s valein

        except SunTimeException as e:
            logging.error("Virhe valojenohjaus.py - (tarkista longitudi ja latitudi): {0}.".format(e))

if __name__ == "__main__":
    ohjausluuppi()
