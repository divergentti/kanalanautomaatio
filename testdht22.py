import paho.mqtt.client as mqtt #mtqq kirjasto
import time
import sys
import Adafruit_DHT #adafruit-kirjasto

mtqqanturi = mqtt.Client("kanalasisa") #MQTT objektin luominen
mtqqanturi.connect("localhost", port=1883, keepalive=60) #Yhteys brokeriin (sama laite)
mtqqanturi.loop_start() #Loopin kaynnistys

kanala_dht22_lampo = "kanalalampo" # subscribe nimi
kanala_dht22_kosteus = "kanalakosteus" #subscribe nimi

while True:
    try:
        kosteus22, lampo22 = Adafruit_DHT.read_retry(22, 4) #22 on sensorin tyyppi, 4 on GPIO pinni, ei fyysinen pinni
       
        if lampo22 is not None:
            lampo22 =  '{:.2f}'.format(lampo22) #desimaaleja 2
            print ("Lampo: ") + str(lampo22)
            mtqqanturi.publish(kanala_dht22_lampo, payload=lampo22, retain=True)
        if kosteus22 is not None:
            kosteus22 = '{:.2f}'.format(kosteus22) #desimaaleja 2
            print ("Kosteus: ") + str(kosteus22)
            mtqqanturi.publish(kanala_dht22_kosteus, payload=kosteus22, retain=True)
        time.sleep(3)
    except (EOFError, SystemExit, KeyboardInterrupt):
        mtqqanturi.disconnect()
        sys.exit()
