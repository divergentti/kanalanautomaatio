#!/usr/bin/env python3
"""
Valojen varsinainen ohjaus tapahtuu mqtt-viesteillä, joita voivat lähettää esimerkiksi lähestymisanturit,
kännykän sovellus tai jokin muu IoT-laite.

Ulkotiloissa valoja on turha sytyttää, jos valoisuus riittää muutenkin. Tieto valoisuudesta saadaan mqtt-kanaviin
valoantureilla, mutta lisätieto auringon nousu- ja laskuajoista voi olla myös tarpeen.

Tämä scripti laskee auringon nousu- ja laskuajat ja lähettää mqtt-komennon valojen päälle kytkemiseen tai sammuttamiseen.

Muuttujina valojen päälläolon suhteen ovat VALOT_POIS_KLO ja VALO_ENNAKKO_AIKA.
- VALOT_POIS tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM)
- VALO_ENNAKKO_AIKA tarkoittaa aikaa jolloin valot sytytetään ennen auringonnousua (string TT:MM).

Ajat ovat paikallisaikaa (parametrit.py-tiedostossa).

Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

2.9.2020 Jari Hiltunen
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
    VALO_ENNAKKO_AIKA

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

aurinko = Sun(LATITUDI, LONGITUDI)
mqttasiakas = mqtt.Client("valojenohjaus-laskettu")  # mqtt objektin luominen, tulla olla uniikki nimi
''' 
Longitudin ja latitudin saat syöttämällä osoitteen esimerkiksi Google Mapsiin.
'''

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2

def alusta():
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
    ''' Scriptin aloituksessa lähetetään varmuuden vuoksi valot pois'''
    try:
        ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
        mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=0, retain=True)
    except OSError:
        print("Virhe %d" % OSError)
        logging.error('Valonohjaus OS-virhe %s' % OSError)
    return

def valojen_ohjaus(status):
    ''' Status on joko 1 tai 0 riippuen siitä mitä releelle lähetetään'''
    """ Tassa kaytetaan salaamatonta porttia ilman TLS:aa, vaihda tarvittaessa """
    try:
        ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
        mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=status, retain=True)
    except OSError:
        print("Virhe %d" % OSError)
        logging.error('Valonohjaus OS-virhe %s' % OSError)
    return


def ohjausluuppi():
    alusta()

    ''' Testaamista varten
    x = 18
    '''

    ''' Muuttujat ja liipaisimet '''
    valot_paalla = False
    ennakko_ajalla = False
    aurinko_noussut = False
    aurinko_laskenut = False

    ''' Tarvitaan päivämäärän ylitystietoa varten'''
    valot_ohjattu_pois = datetime.datetime.strptime('02/02/18 02:02:02', '%m/%d/%y %H:%M:%S')
    valot_ohjattu_paalle = datetime.datetime.strptime('01/01/18 01:01:01', '%m/%d/%y %H:%M:%S')

    """ Suoritetaan looppia kunnes toiminta katkaistaan"""
    while True:
        try:
            aikavyohyke = tz.tzlocal()
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

            time.sleep(10) # suoritetaan 10s valein

        except SunTimeException as e:
            logging.error("Virhe valojenohjaus.py - (tarkista longitudi ja latitudi): {0}.".format(e))

if __name__ == "__main__":
    ohjausluuppi()
