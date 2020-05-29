# suorita python-komennolla!
import paho.mqtt.client as mqtt #mqtt kirjasto
import time
import sys
import Adafruit_DHT #adafruit-kirjasto

mqttanturi = mqtt.Client("kanalasisa-dht22") #mqtt objektin luominen
mqttanturi.username_pw_set("kayttaja","salari") #mqtt useri ja salari
mqttanturi.connect("localhost", port=1883, keepalive=60) #Yhteys brokeriin (sama laite)
mqttanturi.loop_start() #Loopin kaynnistys

kanala_dht22_lampo = "kanala/sisa/lampo"
kanala_dht22_kosteus = "kanala/sisa/kosteus"

while True:
    try:
        kosteus22, lampo22 = Adafruit_DHT.read_retry(22, 4) #22 on sensorin tyyppi, 4 on GPIO pinni, ei fyysinen pinni
       
        if lampo22 is not None:
            lampo22 =  '{:.1f}'.format(lampo22)
            # print ("Lampo: ") + str(lampo22)
            mqttanturi.publish(kanala_dht22_lampo, payload=lampo22, retain=True)
        else:
	 print ("Lampotilatietoa ei saatavilla")
	if kosteus22 is not None:
            kosteus22 = '{:.1f}'.format(kosteus22)
           # print ("Kosteus: ") + str(kosteus22)
            mqttanturi.publish(kanala_dht22_kosteus, payload=kosteus22, retain=True)
	else:
	 print ("Kosteustietoa ei saatavilla")        
	time.sleep(600)
    except (EOFError, SystemExit, KeyboardInterrupt):
        mqttanturi.disconnect()
        sys.exit()
