import utime
import time
import machine
import micropython
import network
import esp
esp.osdebug(None)
#roskankeruuproseduuri
import gc
gc.collect()
from time import sleep
# Parametrit tuodaan parametrit.py-tiedostosta
from parametrit import SSID1, SSID2,SALASANA1,SALASANA2

wificlient_if = network.WLAN(network.STA_IF)
wificlient_if.active(True)

def yhdista_ssid1():
  print("...")
  print("Kaynnistetaan WiFi ...")

  _ = wificlient_if.active(True)
  _ = wificlient_if.connect(SSID1, SALASANA1)

  tmo = 50

  while not wificlient_if.isconnected():
      utime.sleep_ms(100)
      tmo -= 1
      if tmo == 0:
          break

  if tmo > 0:
      ifcfg = wificlient_if.ifconfig()
      print("WiFi yhdistetty, IP:", ifcfg[0])
      utime.sleep_ms(500)


def yhdista_ssid2():
  print("...")
  print("Kaynnistetaan WiFi ...")

  _ = wificlient_if.active(True)
  _ = wificlient_if.connect(SSID2, SALASANA2)

  tmo = 50

  while not wificlient_if.isconnected():
      utime.sleep_ms(100)
      tmo -= 1
      if tmo == 0:
          break

  if tmo > 0:
      ifcfg = wificlient_if.ifconfig()
      print("WiFi yhdistetty, IP:", ifcfg[0])
      utime.sleep_ms(500)

def ei_voida_yhdistaa():
  print("Yhteys ei onnistu. Bootataan 10 s. kuluttua")
  sleep(10)
  #machine.reset()

while not wificlient_if.isconnected():

    try:
        yhdista_ssid1()
    except OSError as e:
        yhdista_ssid2()
    finally:
        print('Yhteydet kunnossa. Jatketaan')
        break

while False:
  ei_voida_yhdistaa()
