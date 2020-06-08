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
  DHT22_LAMPO_KORJAUSKERROIN, DHT22_KOSTEUS_KORJAUSKERROIN, \
  RELE1PINNI, RELE2PINNI

anturi = dht.DHT22(Pin(PINNI_NUMERO))
#virhelaskurin idea on tuottaa bootti jos jokin menee pieleen liian usein
virhe = 0
client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

def rele_tila(rele_ohjaus, msg):
  # Huom! Releet kytketty NC (Normally Closed) jolloin 0 = on
  # Mikali rele kytketty NO (Normally Open), arvo 1 = on
  # Pinni jolla ohjataan rele #1
  rele1 = Pin(RELE1PINNI, Pin.OUT)
  # Pinni jolla ohjataan rele #2
  rele2 = Pin(RELE2PINNI, Pin.OUT)
  #0 = molemmat pois
  #1 = rele 1 on, rele 2 off
  #2 = molemmat on
  #3 = rele 1 off, rele 2 on
  print((rele_ohjaus, msg))
  if rele_ohjaus == RELE_OHJAUS and msg == b'0':
    print('Laita kaikki releet off')
    rele1.value(1)
    rele2.value(1)
  if rele_ohjaus == RELE_OHJAUS and msg == b'1':
    print('Laita rele 1 on, rele 2 off')
    rele1.value(0)
    rele2.value(1)
  if rele_ohjaus == RELE_OHJAUS and msg == b'2':
    print('Laita molemmat releet on')
    rele1.value(0)
    rele2.value(0)
  if rele_ohjaus == RELE_OHJAUS and msg == b'3':
    print('Laita rele 1 off, rele 2 on')
    rele1.value(1)
    rele2.value(0)


def lue_lampo_ja_yhdista():
  global virhe

  try:
    anturi.measure()
  except OSError as e:
    print("Sensoria ei voida lukea!")
    virhe = virhe + 1
    vilkuta_ledi(5)
    return False
  lampo = anturi.temperature() * DHT22_LAMPO_KORJAUSKERROIN
  kosteus = anturi.humidity() * DHT22_KOSTEUS_KORJAUSKERROIN
  print('Lampo: %3.1f C' % lampo)
  print('Kosteus: %3.1f %%' % kosteus)
  vilkuta_ledi(1)
  print("Yhdistetaan mqtt-palvelimeen %s ..." %MQTT_SERVERI)
  client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

  try:
    client.connect()
    #yhdistetaan joka kerran, tulee socket error mosquittoon
  except OSError as e:
    print("Ei voida yhdistaa! ")
    vilkuta_ledi(5)
    virhe = virhe + 1
    return False
  # releen ohjaus
  client.set_callback(rele_tila)
  client.subscribe(RELE_OHJAUS)

  lampo='{:.1f}'.format(lampo)
  kosteus = '{:.1f}'.format(kosteus)

  try:
    client.publish(DHT22_LAMPO, str(lampo))
  except OSError as e:
    print("Arvoa %s ei voida julkistaa! " % str(lampo))
    vilkuta_ledi(5)
    virhe = virhe + 1
    return False
  try:
    client.publish(DHT22_KOSTEUS, str(kosteus))
  except OSError as e:
    print("Arvoa %s ei voida julkistaa! " % str(kosteus))
    vilkuta_ledi(5)
    virhe = virhe + 1
    return False
  vilkuta_ledi(1)
  print('Yhdistetty %s MQTT brokeriin, tallennettu %s %s' % (MQTT_SERVERI, lampo, kosteus))
  print('Tarkistetaan ohjaustietoa...')
  client.check_msg()
  print("Odotetaan seuraavaa arvoa...")
  time.sleep(60)
  virhe = 0
  return True


def restart_and_reconnect():
  print('Ongelmia. Boottaillaan ...')
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

while virhe < 5:
  print("Virhelaskuri: %s" % virhe)
  try:
  lue_lampo_ja_yhdista()
  except OSError as e:
    print("Virhelaskuri: %s" % virhe)
  

#Virheita liikaa
restart_and_reconnect()
