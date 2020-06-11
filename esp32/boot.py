import utime
import time
import machine
import micropython
import network
from ntptime import settime
import esp
esp.osdebug(None)
#roskankeruuproseduuri
import gc
gc.collect()
from time import sleep
# Parametrit tuodaan parametrit.py-tiedostosta
from parametrit import SSID1, SSID2,SALASANA1,SALASANA2
#yhdistetty tieto

wificlient_if = network.WLAN(network.STA_IF)
wificlient_if.active(False)

def yhdista_wifi(ssid_nimi, salasana):
    vilkuta_ledi(1)
    wificlient_if = network.WLAN(network.STA_IF)
    print("Kokeillaan %s" %ssid_nimi)
    wificlient_if.active(True)
    wificlient_if.connect(ssid_nimi, salasana)
    time.sleep(3)
    if wificlient_if.isconnected():
        vilkuta_ledi(2)
        print('Verkon kokoonpano:', wificlient_if.ifconfig())
        yhdistetty = True
        print("Asetetaan aika.")
        try:
            settime()
            print(utime.localtime(utime.time()))
        except:
            print("NTP-palvelimelta pool.ntp.org ei saatu aikaa!")
            ei_voida_yhdistaa()
    return True

def ei_voida_yhdistaa():
  print("Yhteys ei onnistu. Bootataan 10 s. kuluttua")
  vilkuta_ledi(10)
  sleep(10)
  machine.reset()

def vilkuta_ledi(kertaa):
    ledipinni = machine.Pin(2, machine.Pin.OUT)
    for i in range(kertaa):
        ledipinni.on()
        utime.sleep_ms(100)
        ledipinni.off()
        utime.sleep_ms(100)

if yhdista_wifi(SSID1, SALASANA1):
    print("Jatketaan %s verkon kanssa" %SSID1)

elif yhdista_wifi(SSID2, SALASANA2):
    print("Jatketaan %s verkon kanssa" % SSID2)

else:
    ei_voida_yhdistaa()
