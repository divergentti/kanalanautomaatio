#!/usr/bin/env python3
"""
Valojen varsinainen ohjaus tapahtuu mqtt-viesteillä, joita voivat lähettää esimerkiksi lähestymisanturit,
kännykän sovellus tai jokin muu IoT-laite.

Ulkotiloissa valoja on turha sytyttää, jos valoisuus riittää muutenkin. Tieto valoisuudesta saadaan mqtt-kanaviin
valoantureilla, mutta lisätieto auringon nousu- ja laskuajoista voi olla myös tarpeen.

Tämä scripti laskee auringon nousu- ja laskuajat ja lähettää mqtt-komennon valojen päälle kytkemiseen tai sammuttamiseen.

Muuttujina valojen päälläolon suhteen ovat VALO_PAALLAPITO, VALOT_POIS_KLO ja VALO_ENNAKKO_AIKA.
- VALO_PAALLAPITO tarkoittaa aikaa auringon laskun jälkeen, esim. auringonlasku + 2 tuntia (minuutteina integer 120)
- VALOT_POIS tarkoittaa ehdotonta aikaa, jolloin valot laitetaan pois (string TT:MM)
- VALO_ENNAKKO_AIKA tarkoittaa aikaa ennen auringon nousua, esim. 2 tuntia ennen auringon nousua (minuutteina integer 120)

Laskennassa hyödynnetään suntime-scriptiä, minkä voit asentaa komennolla:

pip3 install suntime

30.8.2020 Jari Hiltunen
"""

import paho.mqtt.client as mqtt # mqtt kirjasto
import time
# import syslog  # Syslogiin kirjoittamista varten
import datetime
import logging
from suntime import Sun, SunTimeException
from parametrit import LATITUDI, LONGITUDI, MQTTSERVERIPORTTI, MQTTSERVERI, MQTTKAYTTAJA, MQTTSALARI, \
    VARASTO_POHJOINEN_RELE1_MQTTAIHE_1, VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, VALO_PAALLAPITO, VALOT_POIS_KLO, \
    VALO_ENNAKKO_AIKA

logging.basicConfig(level=logging.ERROR)
logging.error('Virheet kirjataan lokiin')

aurinko = Sun(LATITUDI, LONGITUDI)
''' 
Longitudin ja latitudin saat syöttämällä osoitteen esimerkiksi Google Mapsiin.
'''

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    """ Yhdistetaan mqtt-brokeriin ja tilataan aiheet """
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE1_MQTTAIHE_1)  # tilaa aihe releelle 1
    mqttasiakas.subscribe(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2)  # tilaa aihe releelle 2

def ohjausluuppi():
    """ Tassa kaytetaan salaamatonta porttia ilman TLS:aa, vaihda tarvittaessa """
    broker = MQTTSERVERI  # brokerin osoite
    port = MQTTSERVERIPORTTI
    mqttasiakas = mqtt.Client("valojenohjaus-laskettu")  # mqtt objektin luominen, tulla olla uniikki nimi
    mqttasiakas.username_pw_set(MQTTKAYTTAJA, MQTTSALARI)  # mqtt useri ja salari
    mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin
    mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
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
            ''' Lisäaikaa voi käyttää silloin jos haluaa valojen palavan tietyn ajan auringonlaskun jälkeen  '''
            lisa_aika = auringon_lasku + datetime.timedelta(minutes=VALO_PAALLAPITO)
            ''' Ennakkoaika on aika ennen auringonnousua, jolloin valojen tulisi olla päällä '''
            ennakko_aika = auringon_nousu - datetime.timedelta(minutes=VALO_ENNAKKO_AIKA)
            ''' Valot_pois tarkoittaa aikaa jolloin valot tulee viimeistään sammuttaa päivänpituudesta riippumatta '''
            valot_pois_klo = datetime.datetime.strptime(VALOT_POIS_KLO, '%H:%M')

            '''  print('Aika nyt {}, aurinko nousi {} ja laskee {} UTC'.
               format(aika_nyt.strftime('%H:%M'), auringon_nousu.strftime('%H:%M'), auringon_lasku.strftime('%H:%M'))) '''

            ''' Auringon nousu tai laskulogiikka '''
            if (aika_nyt.replace(tzinfo=None) >= auringon_nousu.replace(tzinfo=None)):
                aurinko_noussut = True
                aurinko_laskenut = False
            if (aika_nyt.replace(tzinfo=None) >= auringon_lasku.replace(tzinfo=None)):
                aurinko_noussut = False
                aurinko_laskenut = True
            ''' Tarkistetaan ollaanko lisäajalla'''
            if (aika_nyt.replace(tzinfo=None) < lisa_aika.replace(tzinfo=None)):
                lisa_aika_paalla = True
            if (aika_nyt.replace(tzinfo=None) >= lisa_aika.replace(tzinfo=None)):
                lisa_aika_paalla = False
            ''' Tarkistetaan ollaanko päälläpitoajalla '''
            if (aika_nyt.replace(tzinfo=None) < valot_pois_klo.replace(tzinfo=None)):
                paalla_pito_ajalla = True
            if (aika_nyt.replace(tzinfo=None) >= valot_pois_klo.replace(tzinfo=None)):
                paalla_pito_ajalla = False
            ''' Tarkistetaan ollaanko ennakkoajalla '''
            if aika_nyt.replace(tzinfo=None) >= ennakko_aika.replace(tzinfo=None):
                ennakko_ajalla = True
            if aika_nyt.replace(tzinfo=None) < ennakko_aika.replace(tzinfo=None):
                ennakko_ajalla = False

            ''' Valojen sytytys ja sammutuslogiikka'''
            if (aurinko_laskenut == True) and (paalla_pito_ajalla == True) and (valot_paalla == False):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=1, retain=True)
                    valot_paalla = True
                    print ("Valot sytytetty paallapitoajan mukaisesti.")
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            if (aurinko_laskenut == True) and (paalla_pito_ajalla == False) and (valot_paalla == True):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 0 tarkoittaa pois päältä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=0, retain=True)
                    print("Valot sammutettu paallapitoajan mukaisesti.")
                    valot_paalla = False
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            ''' !! Emme huomioi sitä jos lisäaika on myöhäisempi kuin sammutusaika !! '''
            if (aurinko_laskenut == True) and (lisa_aika_paalla == True) and (valot_paalla == False):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=1, retain=True)
                    valot_paalla = True
                    print("Valot sytytetty lisa-ajan mukaisesti")
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            if (aurinko_laskenut == True) and (lisa_aika_paalla == False) and (valot_paalla == True):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 0 tarkoittaa pois päältä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=0, retain=True)
                    valot_paalla = True
                    print("Valot sammutettu lisa-ajan mukaisesti")
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            if (aurinko_laskenut == True) and (ennakko_ajalla == True) and (valot_paalla == False):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 1 tarkoittaa päällä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=1, retain=True)
                    valot_paalla = True
                    print("Valot sytytetty ennakkoajan mukaisesti")
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)
            if (aurinko_laskenut == True) and (ennakko_ajalla == False) and (valot_paalla == True):
                try:
                    ''' mqtt-sanoma voisi olla esim. koti/ulko/etela/valaistus ja rele 0 tarkoittaa pois päältä '''
                    mqttasiakas.publish(VARASTO_POHJOINEN_RELE2_MQTTAIHE_2, payload=0, retain=True)
                    valot_paalla = False
                    print("Valot sammutettu ennakkoajan mukaisesti")
                except OSError:
                    print("Virhe %d" % OSError)
                    logging.error('Valonohjaus OS-virhe %s' % OSError)

            time.sleep(10) # suoritetaan 10s valein

        except SunTimeException as e:
            logging.error("Virhe valojenohjaus.py - (tarkista longitudi ja latitudi): {0}.".format(e))

if __name__ == "__main__":
    ohjausluuppi()
