#!/usr/bin/python

'''
Waveshare SX126X LoRa HAT send/receive demo

This product is a Raspberry Pi expansion board based on the Semtec SX1268/SX1262 chip.
The chipset has a wireless serial port module and embedded firmware for LoRa modulation.
With this demo script, users may transfer or receive data directly via UART.  
Setting parameters such as coderate, spread factor and so on is not required.

Prior to executing the demo, your device's serial port must first be configured.
Execute: sudo 'raspi-config' and choose Interface Options > Serial Port.
Disable the serial login shell, enable the serial interface, then reboot. 
With the LoRa HAT attached to RPi, the M0 and M1 jumpers should be removed.

Note that the SX1262 LoRa HAT does NOT suport the LoRaWAN protocol.

This script is primarily for Raspberry Pi models 3B+, 4B, and the Zero series.

Original source modified by @billz
@author Bill Zimmerman <billzimmerman@gmail.com>
@see https://github.com/MithunHub/LoRa 
@link https://www.waveshare.com/wiki/SX1262_868M_LoRa_HAT
@license https://github.com/wirelesscookbook/blob/master/LICENSE
'''

import sys
import sx126x
import threading
import time
import select
import termios
import tty
import os
from threading import Timer
from dotenv import load_dotenv

load_dotenv()
old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())

def boolean(s):
    return s.lower() in ['true', 'yes', '1']

# Set default values from .env
serial_num = os.getenv('SERIAL_INTERFACE')
freq = int(os.getenv('FREQUENCY'))
addr = int(os.getenv('ADDRESS'))
power = int(os.getenv('POWER'))
rssi = boolean(os.getenv('RSSI'))
air_speed = int(os.getenv('AIR_SPEED'))
relay = boolean(os.getenv('RELAY'))

#   Obtain the temprature of the RPi CPU 
def get_cpu_temp():
    tempFile = open( "/sys/class/thermal/thermal_zone0/temp" )
    cpu_temp = tempFile.read()
    tempFile.close()
    return float(cpu_temp)/1000

#   serial_num
#       PiZero, Pi3B+, and Pi4B use "/dev/ttyS0"
#
#    Frequency is [850 to 930], or [410 to 493] MHz
#
#    address is 0 to 65535
#        When using the same frequency, if 65535 is set the node can receive 
#        messages from another node if its address is 0 to 65534. Similarly,
#        if the address value is 0 to 65534 the node can receive messages from 
#        a sending note with an address value of 65535.
#        Otherwise the two nodes must use the same address and frequency.
#
#    The tramsmit power is {10, 13, 17, and 22} dBm
#
#    RSSI (receive signal strength indicator) is {True or False}
#        It will print the RSSI value when it receives each message

print("Starting the SX1262 LoRa Demo...")
print("Serial interface: " + serial_num)
print("Frequency: " + str(freq) + " MHz")
print("Node address: " + str(addr))
print("Power: " + str(power))
print("RSSI: " + str(rssi))
print("Air speed: " + str(air_speed))
print("================")

node = sx126x.sx126x(serial_num,freq,addr,power,rssi,air_speed,relay)

def send_deal():
    get_rec = ""
    print("")
    print("Enter a message such as: \033[1;32mHello World\033[0m")
    print("This will send 'Hello World' to a LoRa node with device address " + str(addr) + " on frequency " + str(freq) +" MHz.")
    print("Input your message followed by Enter: ",end='',flush=True)

    while True:
        rec = sys.stdin.read(1)
        if rec != None:
            if rec == '\x0a': break
            get_rec += rec
            sys.stdout.write(rec)
            sys.stdout.flush()

    get_t = get_rec.split(",")
    offset_frequency = int(freq)-(850 if int(freq)>850 else 410)

    # the sending message format
    #
    #         receiving node              receiving node                   receiving node           own high 8bit           own low 8bit                 own 
    #         high 8bit address           low 8bit address                    frequency                address                 address                  frequency             message payload
    data = bytes([int(addr)>>8]) + bytes([int(addr)&0xff]) + bytes([offset_frequency]) + bytes([node.addr>>8]) + bytes([node.addr&0xff]) + bytes([node.offset_freq]) + get_t[0].encode()

    node.send(data)
    print('\x1b[2A',end='\r')
    print(" "*200)
    print(" "*200)
    print(" "*200)
    print('\x1b[3A',end='\r')

def send_cpu_continue(continue_or_not = True):
    if continue_or_not:
        global timer_task
        global seconds
        
        # Broadcast the cpu temperature at 868.125MHz
        data = bytes([255]) + bytes([255]) + bytes([18]) + bytes([255]) + bytes([255]) + bytes([12]) + "CPU Temperature: ".encode()+str(get_cpu_temp()).encode()+" C".encode()
        node.send(data)
        time.sleep(0.2)
        timer_task = Timer(seconds,send_cpu_continue)
        timer_task.start()
    else:
        data = bytes([255]) + bytes([255]) + bytes([18]) + bytes([255]) + bytes([255]) + bytes([12]) + "CPU Temperature: ".encode()+str(get_cpu_temp()).encode()+" C".encode()
        node.send(data)
        time.sleep(0.2)
        timer_task.cancel()
        pass

try:
    time.sleep(1)
    print("Press \033[1;32mEsc\033[0m to exit")
    print("Press \033[1;32mi\033[0m   to send a message")
    print("Press \033[1;32ms\033[0m   to send CPU temperature every 10 seconds")
    
    # send rpi cpu temperature at 10 second intervals
    seconds = 10
    
    while True:

        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            c = sys.stdin.read(1)

            # dectect key Esc
            if c == '\x1b': break
            # dectect key i
            if c == '\x69':
                send_deal()
            # dectect key s
            if c == '\x73':
                print("Press \033[1;32mc\033[0m   to exit the send task")
                timer_task = Timer(seconds,send_cpu_continue)
                timer_task.start()
                
                while True:
                    if sys.stdin.read(1) == '\x63':
                        timer_task.cancel()
                        print('\x1b[1A',end='\r')
                        print(" "*100)
                        print('\x1b[1A',end='\r')
                        break

            sys.stdout.flush()
            
        node.receive()
        
        # timer,send messages automatically
        
except:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

