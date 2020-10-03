""" Boottiversio 1.0

Parametrit tuodaan parametrit.py-tidesosta. Vähintään tarvitaan SSID1 ja SALASANA1 joilla kerrotaan
mihin Wifi-AP halutaan yhdistää. Mikäli WebREPL:ä halutaan käyttää, tulee ensimmäisellä kerralla
käynnistää komento import webrepl_setup, joka luo tiedoston webrepl_cfg.py laitteen juureen.

Komennoilla import os, os.rename('vanha_tiedosto', 'uusi_tiedosto') tai os.remove('tiedostonimi')
voit käsitellä laitteen tiedostoja joko WebREPL tai konsoliportin kautta.

3.10.2020 Jari Hiltunen """


import utime
import time
import machine
import network
import ntptime
import esp
import webrepl
from time import sleep
from parametrit import SSID1, SSID2, SALASANA1, SALASANA2, WEBREPL_SALASANA, NTPPALVELIN, DHCP_NIMI

machine.freq(240000000)  # Aluksi maksimipotku prosessoriin
esp.osdebug(None)
wificlient_if = network.WLAN(network.STA_IF)
wificlient_if.active(False)


def yhdista_wifi(ssid_nimi, salasana):
    global wificlient_if
    print("Kokeillaan %s" % ssid_nimi)
    wificlient_if.active(True)
    if DHCP_NIMI is not None:
        wificlient_if.config(dhcp_hostname=DHCP_NIMI)
    wificlient_if.connect(ssid_nimi, salasana)
    time.sleep(2)
    if wificlient_if.isconnected():
        aseta_aika()
        return True
    else:
        return False


def ei_voida_yhdistaa():
    print("Yhteys ei onnistu. Bootataan 1 s. kuluttua")
    sleep(1)
    machine.reset()


def aseta_aika():
    try:
        if NTPPALVELIN is not None:
            ntptime.host = NTPPALVELIN
        ntptime.settime()
    except OSError as e:
        print("NTP-palvelimelta %s ei saatu aikaa! Virhe %s" % (NTPPALVELIN, e))
        ei_voida_yhdistaa()


def jatka():
    """
    :rtype: wificlient_if
    """
    if WEBREPL_SALASANA is not None:
        try:
            webrepl.start(password=WEBREPL_SALASANA)
            webrepl.start()
        except OSError as e:
            print("WebREPL ei kaynnisty. Virhe %s" % e)
            ei_voida_yhdistaa()
    print("Aika: %s " % utime.localtime(utime.time()))
    print('Verkon kokoonpano:', wificlient_if.ifconfig())
    print("WiFi signaalitaso %s" % (wificlient_if.status('rssi')))
    machine.freq(80000000)  # hidastetaan


if wificlient_if.isconnected() is True:
    jatka()


if SSID1 is None and SSID2 is None:
    print("Aseta SSID1 ja/tai SSID2 nimi ja salasana paramterit.py-tiedostossa!")
    raise Exception("Aseta SSID1 ja/tai SSID2 nimi ja salasana paramterit.py-tiedostossa!")


if wificlient_if.isconnected() is False:
    if SSID1 is not None and SALASANA1 is not None:
        try:
            yhdista_wifi(SSID1, SALASANA1)
        except False:
            if SSID2 is not None and SALASANA2 is not None:
                try:
                    yhdista_wifi(SSID2, SALASANA2)
                except False:
                    print("Yhdistys ei onnistu, bootataan!")
                    ei_voida_yhdistaa()
else:
    jatka()
