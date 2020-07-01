#!/usr/bin/env python
# Lukee reed-releen tilaa ja lähettää tiedon mqtt-brokerille
# 1.7.2020 Jari Hiltunen
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt # mqtt kirjasto
import time

reed_pinni = 36 # gpio 16
broker = "localhost" #brokerin osoite
port = 1883 #portti
# releelle tilattava mtqq-aihe
MQTTAIHE = 'kanala/ulko/luukkukytkin' # aihe jolle tieto julkaistaan

def mqttyhdista(mqttasiakas, userdata, flags, rc):
    # print("Yhdistetty " + str(rc))
    # Yhdistetaan brokeriin ja tilataan aiheet
    mqttasiakas.subscribe(MQTTAIHE)  # tilaa aihe reed releelle

def alustus():
    try:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(reed_pinni, GPIO.IN, pull_up_down=GPIO.PUD_UP) # jannite paalla
    except OSError:
        print("Virhe %d" %OSError)
        GPIO.cleanup()
        return False

def reedStatus(channel):
    # 1 = reed on
    # 0 = reed off
    if GPIO.input(reed_pinni):
        print ("Reed status on")
        try:
            mqttasiakas.publish(MQTTAIHE, payload=1, retain=True)
        except OSError:
            print("Virhe %d" % OSError)
            GPIO.cleanup()
            return False
    else:
        print ("Reed pois")
        try:
            mqttasiakas.publish(MQTTAIHE, payload=0, retain=True)
        except OSError:
            print("Virhe %d" % OSError)
            GPIO.cleanup()
            return False

def looppi():
    try:
        GPIO.add_event_detect(reed_pinni,GPIO.BOTH, callback=reedStatus, bouncetime=20)
    except OSError:
        print("Virhe %d" %OSError)
        GPIO.cleanup()
        return False
    while True:
            time.sleep(0.01)  # prosessorikuorman laskua varten
            pass

def vapauta():
    GPIO.cleanup()  # Vapautetaan resurssit

# mqtt-objektin luominen
mqttasiakas = mqtt.Client("reed-luukku")  # mqtt objektin luominen
mqttasiakas.on_connect = mqttyhdista  # mita tehdaan kun yhdistetaan brokeriin
mqttasiakas.username_pw_set("useri","salari")  # mqtt useri ja salari
mqttasiakas.connect(broker, port, keepalive=60, bind_address="")  # yhdista mqtt-brokeriin

if __name__ == '__main__':     # Sovelluksen aloitus
    alustus()
try:
    looppi()
except KeyboardInterrupt:  # Ctrl + C vapauttaa resurssit
    vapauta()
