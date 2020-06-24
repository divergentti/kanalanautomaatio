# kaksi eri vaihtoehtoista tapaa lukea RDM6300 RFID-kortinlukijaa
# 1) pip3 install rdm6300
# 2) suoraan sarjaportista luku
# Molempiin tarvitaan seuraavat muutokset:
# Bluetoothin poistaminen UART0:sta
# sudo nano /boot/config.txt lisaa rivit:
# enable_uart=1
# core_freq=250
# sudo systemctl disable hciuart.service
# sudo systemctl disable bluealsa.service
# sudo systemctl disable bluetooth.service
# sudo raspi-config, 5 Interfacing, P6 Serial -> No konsolille, yes serial portille
# sudo nano /boot/cmdline.txt ja sielta console=tty1 pois
# sudo apt-get install python-serial
# testailla voit suoraan asentamalla sudo apt-get install minicom
# minicom -D /dev/ttyS0 ja siella ctrl + a, z, p, c =9600 
# RDM6300 kytketty nasta 1 (txd) Raspi GPIO15 (pinni 10, rxd) ja nasta 2 (rxd) raspin GPIO14 (pinni 8, txd)
# RDM6300 ja Raspin valilla tasomuunnin 3,3V -> 5V (voi tehda vastuksilla)
import time
import serial 
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
# rdm6300 luku: 
import rdm6300

reader = rdm6300.Reader('/dev/ttyS0')
#reader = rdm6300.Reader('/dev/ttyAMA0')
print("Aseta luettava tagi")

while True:
    try:
        card = reader.read()
        if card:
            print(f"[{card.value}] luettiin kortti: {card}")
    except KeyboardInterrupt: # Ctrl+C
       print("Nappiskeskeytys")
    
    except:
        print("virhe") 

    finally:
       print("tee jotain") 
      
 
# Sarjaporttiluku: 

#PortRF = serial.Serial('/dev/ttyS0',9600)

#while True:
#    try:
#        read_byte = PortRF.read()
#        print (read_byte)
        
#    except KeyboardInterrupt: # Ctrl+C:
#        print("Nappiskeskeytys")
#    except:
#        print("virhe") 

#    finally:
#        print("puhdista portit") 
#        GPIO.cleanup() # kaikkien GPIO nollaus 
        
