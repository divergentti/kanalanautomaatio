import paho.mqtt.client as mqtt # Tuo MQTT kirjasto
import time # aikakirjasto delayta varten
import random

# Viestitapahtuma
def viestiToiminto (clientti, vdata, viesti):
	aihe = str(viesti.topic)
	viesti = str(viesti.payload.decode("utf-8"))
	# print(aihe + viesti)

kanalaLampo = mqtt.Client("kanalalampo_mqtt") # Luodaan MQTT client objekti
kanalaLampo.connect("localhost", 1883) # Yhdistetaan MQTT-brokeri
#kanalaLampo.subscribe("Lampotila") # Tilataan Lampotila-aiheiset viestit
kanalaLampo.on_message = viestiToiminto # Liitetaan edella esitetty viestiToiminto tilaukseen
kanalaLampo.loop_start() # Kaynnista MQTT clientti

# Ohjelman looppi

while(1):
        localtime = time.asctime( time.localtime(time.time()) )
	kanalaLampo.publish("Lampotila", localtime  +  " Temp:" + str( random.randint(1, 35))) # Julkaise viesti MQTT brokerille
	time.sleep(1) # Venttaa sekunti
