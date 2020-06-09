#tarkoitettu ESP32-Wroom-32 NodeMCU:lle
#Lukee DHT22-anturia ja ohjaa 2-kanavaista reletta
#Parametrit tuodaan parametrit.py-tiedostosta
#Yksi ledin vilaus = toiminta alkaa
#Kaksi ledin vilautusta = toiminta saatettu loppuun
#10 ledin vilautusta = virhe!
#Osa kanalan automaatioprojektia, https://hiltsu.dy.fi
#Jari Hiltunen 9.6.2020
import time
import utime
import machine
import micropython
import dht
from machine import Pin
from umqttsimple import MQTTClient

#tuodaan parametrit tiedostosta parametrit.py
from parametrit import CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, \
  MQTT_SALASANA, DHT22_LAMPO, DHT22_KOSTEUS, RELE_OHJAUS, PINNI_NUMERO, \
  DHT22_LAMPO_KORJAUSKERROIN, DHT22_KOSTEUS_KORJAUSKERROIN, \
  RELE1PINNI, RELE2PINNI
#dht-kirjasto tukee muitakin antureita kuin dht22
anturi = dht.DHT22(Pin(PINNI_NUMERO))
#virhelaskurin idea on tuottaa bootti jos jokin menee pieleen liian usein
anturivirhe = 0
relevirhe = 0
client = MQTTClient(CLIENT_ID, MQTT_SERVERI, MQTT_PORTTI, MQTT_KAYTTAJA, MQTT_SALASANA)

def mqtt_palvelin_yhdista():
  try:
    client.connect()
  except OSError as e:
    print("Ei voida yhdistaa! ")
    client.disconnect()
    time.sleep(60)
    restart_and_reconnect()
    return False
  # releen ohjaus
  client.set_callback(rele_tila)
  client.subscribe(RELE_OHJAUS)
  return True

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
  # testataan onko tullut uusi arvo vai ei

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
  vilkuta_ledi(2)
  time.sleep(1)

def lue_releen_status():
  global relevirhe
  vilkuta_ledi(1)
  print('Tarkistetaan releen ohjaustietoa...')
  try:
    client.check_msg()
  except OSError as e:
    print("Releviestin lukuvirhe!")
    relevirhe = relevirhe + 1
    return False
  vilkuta_ledi(2)
  relevirhe = 0
  return True


def lue_lampo_ja_yhdista():
  global anturivirhe
  vilkuta_ledi(1)
  try:
    anturi.measure()
  except OSError as e:
    print("Sensoria ei voida lukea!")
    anturivirhe = anturivirhe + 1
    return False
  lampo = anturi.temperature() * DHT22_LAMPO_KORJAUSKERROIN
  kosteus = anturi.humidity() * DHT22_KOSTEUS_KORJAUSKERROIN
  print('Lampo: %3.1f C' % lampo)
  print('Kosteus: %3.1f %%' % kosteus)
  print("Tallenntaan arvot mqtt-palvelimeen %s ..." %MQTT_SERVERI)
  lampo='{:.1f}'.format(lampo)
  kosteus = '{:.1f}'.format(kosteus)

  try:
    client.publish(DHT22_LAMPO, str(lampo))
  except OSError as e:
    print("Arvoa %s ei voida tallentaa! " % str(lampo))
    anturivirhe = anturivirhe + 1
    return False
  try:
    client.publish(DHT22_KOSTEUS, str(kosteus))
  except OSError as e:
    print("Arvoa %s ei voida tallentaa! " % str(kosteus))
    anturivirhe = anturivirhe + 1
    return False
  print('Tallennettu %s %s' % (lampo, kosteus))
  anturivirhe = 0
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

def anturiluuppi():
 while anturivirhe < 5:
  print("Anturiluupin virhelaskuri: %s" % anturivirhe)
  try:
    lue_lampo_ja_yhdista()
  except OSError as e:
    print("Anturiluupin virhelaskuri: %s" % anturivirhe)
    # Virheita liikaa
    restart_and_reconnect()
  time.sleep(20)
  yield None

def releluuppi():
 while relevirhe < 5:
  print("Releloopin virhelaskuri: %s" % relevirhe)
  try:
    lue_releen_status()
  except OSError as e:
    print("Releloopin virhelaskuri: %s" % relevirhe)
    # Virheita liikaa
    restart_and_reconnect()
  time.sleep(10)
  yield None

#annetaan verkon tasaantua par isekkaa
time.sleep(2)

try:
  mqtt_palvelin_yhdista()
except OSError as e:
  print("Ei onnistunut yhteys mqtt-palvelimeen %s" % MQTT_SERVERI)
  restart_and_reconnect()

TehtavaJono = [anturiluuppi(), releluuppi()]

while True:
  # loopataan ellei virheita muodostu
  for task in TehtavaJono:
    next(task)

# Jos kaikki menee pieleen
restart_and_reconnect()
