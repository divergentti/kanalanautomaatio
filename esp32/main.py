import time
import machine
import micropython
import dht
from machine import Pin
from umqttsimple import MQTTClient
#tuodaan parametrit
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
  MQTT_SALASANA, DHT22_LAMPO, DHT22_KOSTEUS, RELE_OHJAUS, PINNI_NUMERO
ANTURI = dht.DHT22(Pin(PINNI_NUMERO))

def rele_tila(rele_ohjaus, msg):
  print((rele_ohjaus, msg))
  if rele_ohjaus == b'kanala/ulko/rele' and msg == b'on':
    print('Laita rele on')
    #jatka koodia

def connect_and_subscribe():
  client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)
  client.set_callback(rele_tila)
  client.connect()
  client.subscribe(RELE_OHJAUS)
  print('Yhdistetty %s MQTT brokeriin, tilattu %s aihe' % (MQTT_SERVERI, RELE_OHJAUS))
  return client

def tallenna_tiedot():
  client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)
  client.connect()
  lampo, kosteus = lue_dht_anturi()
  if lampo is not None:
    lampo='{:.1f}'.format(lampo)
  if kosteus is not None:
    kosteus = '{:.1f}'.format(kosteus)
  client.publish(DHT22_LAMPO, str(lampo))
  client.publish(DHT22_KOSTEUS, str(kosteus))
  time.sleep(60)
  # lukudelay
  print('Yhdistetty %s MQTT brokeriin, tallennettu %s %s' % (MQTT_SERVERI, lampo, kosteus))
  return client

def restart_and_reconnect():
  print('Yhteys MQTT brokeriin ei onnistunut. Uusi yritys 10s...')
  time.sleep(10)
  machine.reset()
  #resetoidaan

def lue_dht_anturi():
  try:
    ANTURI.measure()
    lampo22 = ANTURI.temperature()
    kosteus22 = ANTURI.humidity()
    print('Lampo: %3.1f C' % lampo22)
    print('Kosteus: %3.1f %%' % kosteus22)
    return lampo22, kosteus22
  except OSError as e:
    return ('Sensoria ei voi lukea.')

try:
    client = connect_and_subscribe()
except OSError as e:
    restart_and_reconnect()

while True:
  try:
    client = tallenna_tiedot()
  except OSError as e:
    restart_and_reconnect()
