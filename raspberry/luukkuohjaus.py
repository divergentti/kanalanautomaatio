#!/usr/bin/env python3
# scripti kuuntelee mqtt-viestia siita laitetaanko luukku pois tai paalle
# taman jalkeen lahetetaan ennakolta tutkittu kaukosaatimen koodi
#
# 22.06.2020 Jari Hiltunen
# 433MHz ohjaus kutsutaan erillista koodia crontabin vuoksi


import paho.mqtt.client as mqtt #mqtt kirjasto
import subprocess # shell-komentoja varten
aiempiviesti = None  # aiempi tilaviesti

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    print("Yhdistetty " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aihe
    mqttasiakas.subscribe(MQTTAIHE)

def mqttviesti(mqttasiakas, userdata, message):
    global aiempiviesti # ei toteuteta jos ei muutosta
    viesti = int(message.payload)
    if (viesti < 0) or (viesti > 1):
        print("Virheellinen arvo!")
        return False
    if (viesti == 0) and (viesti != aiempiviesti):
        print("Lahetaan kiinni")
        try:
            # samaa scrptia kutsutaan crobtabissa ajastettuna, siksi toteutus tama
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-kiinni', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
        except OSError:
            print("Virhe %d" %OSError)
            return False
        # print(suorita.returncode)
        aiempiviesti = 0
        return True
    if (viesti == 1) and (viesti != aiempiviesti):
        print("Lahetaan auki")
        try:
            suorita = subprocess.Popen('/home/pi/Kanala/kanala-auki', shell=True, stdout=subprocess.PIPE)
            suorita.wait()
        except OSError:
            print("Virhe %d" %OSError)
            return False
        aiempiviesti = 1
        return True
    return

broker = "localhost" #brokerin osoite
port = 1883 #portti
MQTTAIHE = 'kanala/ulko/luukku' # aihe josta luukun status luetaan

# mqtt-objektin luominen
mqttasiakas = mqtt.Client("luukku-broker") #mqtt objektin luominen
mqttasiakas.on_connect = mqttyhdista # mita tehdaan kun yhdistetaan brokeriin
mqttasiakas.on_message = mqttviesti # maarita mita tehdaan kun viesti saapuu
mqttasiakas.username_pw_set("useri","salari") #mqtt useri ja salarittanturi.connect("localhost", port=1883, keepalive=60) #Yhteys brokeriin (sama laite)
mqttasiakas.connect(broker, port, keepalive=60, bind_address="") #yhdista mqtt-brokeriin
mqttasiakas.subscribe(MQTTAIHE) # tilaa aihe

kaynnissa = True
while True:
    mqttasiakas.loop_start()
    # mqttasiakas.loop_forever()

