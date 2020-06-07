import time
import utime
import machine
import micropython
import dht
from machine import Pin
from umqttsimple import MQTTClient

#tuodaan parametrit
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
  MQTT_SALASANA, DHT22_LAMPO, DHT22_KOSTEUS, RELE_OHJAUS, PINNI_NUMERO, \
  DHT22_LAMPO_KORJAUSKERROIN, DHT22_KOSTEUS_KORJAUSKERROIN

anturi = dht.DHT22(Pin(PINNI_NUMERO))
#anturi = dht.DHT22(machine.Pin(4))

def rele_tila(rele_ohjaus, msg):
  print((rele_ohjaus, msg))
  if rele_ohjaus == RELE_OHJAUS and msg == b'on':
    print('Laita rele on')
    #jatka koodia

def connect_and_subscribe():
  print("Yhdistetaan mqtt-palvelimeen %s ja tilataan aihe %s..." % (MQTT_SERVERI, RELE_OHJAUS))
  client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)
  try:
    client.connect()
  except OSError as e:
    return False
  client.set_callback(rele_tila)
  client.subscribe(RELE_OHJAUS)
  print('Yhdistetty %s MQTT brokeriin, tilattu %s aihe' % (MQTT_SERVERI, RELE_OHJAUS))
  vilkuta_ledi(1)
  return True


def tallenna_lampo_kosteus_tiedot():
  try:
    anturi.measure()
  except OSError as e:
    print("Sensoria ei voida lukea!")
    vilkuta_ledi(5)
  lampo = anturi.temperature() * DHT22_LAMPO_KORJAUSKERROIN
  kosteus = anturi.humidity() * DHT22_KOSTEUS_KORJAUSKERROIN
  print('Lampo: %3.1f C' % lampo)
  print('Kosteus: %3.1f %%' % kosteus)
  vilkuta_ledi(1)
  print("Yhdistetaan mqtt-palvelimeen %s ..." %MQTT_SERVERI)
  client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)
  lampo='{:.1f}'.format(lampo)
  kosteus = '{:.1f}'.format(kosteus)
  try:
    client.connect()
  except OSError as e:
    print("Yhteys mqtt-palvelimeen ei onnistunut!")
    vilkuta_ledi(5)
  try:
    client.publish(DHT22_LAMPO, str(lampo))
  except OSError as e:
    print("Arvoa %s ei voida julkistaa! " % str(lampo))
    vilkuta_ledi(5)
  try:
    client.publish(DHT22_KOSTEUS, str(kosteus))
  except OSError as e:
    print("Arvoa %s ei voida julkistaa! " % str(kosteus))
    vilkuta_ledi(5)
  vilkuta_ledi(1)
  print('Yhdistetty %s MQTT brokeriin, tallennettu %s %s' % (MQTT_SERVERI, lampo, kosteus))
  time.sleep(60)
  return True


def restart_and_reconnect():
  print('Yhteys MQTT brokeriin ei onnistunut. Uusi yritys 10s...')
  vilkuta_ledi(10)
  time.sleep(5)
  machine.reset()
  #resetoidaan

def vilkuta_ledi(kertaa):
  ledipinni = machine.Pin(2, machine.Pin.OUT)
  for i in range(kertaa):
    ledipinni.on()
    utime.sleep_ms(100)
    ledipinni.off()
    utime.sleep_ms(100)

try:
  client = connect_and_subscribe()
except OSError as e:
  print("Ei onnaa1")
  #restart_and_reconnect()

while True:
  tallenna_lampo_kosteus_tiedot()
    #restart_and_reconnect()
