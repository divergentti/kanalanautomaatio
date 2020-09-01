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

Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

1.9.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt # mqtt kirjasto
import time
# import syslog  # Syslogiin kirjoittamista varten
import datetime
import logging
from suntime import Sun, SunTimeException
from parametrit import LATITUDI, LONGITUDI, MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALOT_POIS_KLO, \
    VALO_ENNAKKO_AIKA

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

aurinko = Sun(LATITUDI, LONGITUDI)
''' 
Longitudin ja latitudin saat syöttämällä osoitteen esimerkiksi Google Mapsiin.
'''

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2

def alusta():
    global mqttasiakas
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttasiakas = mqtt.Client("valojenohjaus-laskettu")  # mqtt objektin luominen, tulla olla uniikki nimi
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin

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
    ''' Muuttujat ja liipaisimet '''
    valot_paalla = False
    lisa_aika_paalla = False
    paalla_pito_ajalla = False
    ennakko_ajalla = False
    aurinko_noussut = False
    aurinko_laskenut = False

    """ Suoritetaan looppia kunnes toiminta katkaistaan"""
    while True:
        try:
            auringon_nousu = aurinko.get_sunrise_time()
            auringon_lasku = aurinko.get_sunset_time()
            aika_nyt = datetime.datetime.utcnow()
            ''' Testaamista varten '''
            #  aika_nyt = aika_nyt.replace(hour=5, minute=00)
            ''' Kelloaika ennen auringonnousua jolloin valot tulisi laittaa päälle '''
            tunnit1, minuutit1 = map(int, VALO_ENNAKKO_AIKA.split(':'))
            ennakko_aika = aika_nyt.replace(hour=tunnit1, minute=minuutit1)

            ''' Valot_pois tarkoittaa aikaa jolloin valot tulee viimeistään sammuttaa päivänpituudesta riippumatta '''
            tunnit, minuutit = map(int, VALOT_POIS_KLO.split(':'))
            valot_pois_klo = aika_nyt.replace(hour=tunnit, minute=minuutit)

            '''  print('Aika nyt {}, aurinko nousi {} ja laskee {} UTC'.
               format(aika_nyt.strftime('%H:%M'), auringon_nousu.strftime('%H:%M'), auringon_lasku.strftime('%H:%M'))) '''

            ''' Auringon nousu tai laskulogiikka '''
            if (aika_nyt.replace(tzinfo=None) >= auringon_nousu.replace(tzinfo=None)):
                aurinko_noussut = True
                aurinko_laskenut = False
            if (aika_nyt.replace(tzinfo=None) >= auringon_lasku.replace(tzinfo=None)):
                aurinko_noussut = False
                aurinko_laskenut = True

            ''' Tarkistetaan ollaanko päälläpitoajalla '''
            if (aika_nyt.replace(tzinfo=None) < valot_pois_klo.replace(tzinfo=None) and \
                    (aika_nyt.replace(tzinfo=None) > auringon_nousu.replace(tzinfo=None)) and \
                    (aurinko_laskenut == True)):
                paalla_pito_ajalla = True
            if (aika_nyt.replace(tzinfo=None) >= valot_pois_klo.replace(tzinfo=None) and \
                    (aika_nyt.replace(tzinfo=None) > auringon_nousu.replace(tzinfo=None)) and \
                    (aurinko_laskenut == True)):
                paalla_pito_ajalla = False

            ''' Valojen sytytys ja sammutuslogiikka'''

            ''' Jos aurinko on laskenut, sytytetään valot'''
            if (aurinko_laskenut == True) and (valot_paalla == False) and (paalla_pito_ajalla == True):
                valojen_ohjaus(1)
                valot_paalla = True
                print("Aurinko laskenut. Valot sytytetty.")

            ''' Jos aurinko noussut, sammutetaan valot '''
            if (aurinko_noussut == True) and (valot_paalla == True):
                valojen_ohjaus(0)
                valot_paalla = False
                ennakko_ajalla = False
                print("Aurinko noussut. Valot sammutettu.")

            ''' Valot päällä jos aurinko laskenut. Katsotaan tuleeko valot sammuttaa.'''
            if (aurinko_laskenut == True) and (paalla_pito_ajalla == False) and (valot_paalla == True):
                valojen_ohjaus(0)
                valot_paalla = False
                print("Valot sammutettu paallapitoajan loppumisen vuoksi.")

            ''' Tarkistetaan ollaanko ennakkoajalla'''

            if (valot_pois_klo.replace(tzinfo=None) > aika_nyt.replace(tzinfo=None)) and \
                    (aika_nyt.replace(tzinfo=None) >= ennakko_aika.replace(tzinfo=None)):
                ennakko_ajalla = True

            ''' Valot pois, aurinko nousee kohta, laitetaan valot ennakolta päälle '''
            if (aurinko_laskenut == True) and (ennakko_ajalla == True) and (valot_paalla == False):
                valojen_ohjaus(1)
                valot_paalla = True
                print("Valot sytytetty ennakkoajan mukaisesti")

            time.sleep(10) # suoritetaan 10s valein

        except SunTimeException as e:
            logging.error("Virhe valojenohjaus.py - (tarkista longitudi ja latitudi): {0}.".format(e))

if __name__ == "__main__":
    ohjausluuppi()
