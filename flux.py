#!/usr/bin/env python
# Smart Bulb Flux Bulb Control With Bluez
# Author: Tony DiCola
# Author: (Flux Bulb modifications) Jeremy Plichta
# Author: (Added lots of functionality) Eric Schiesser
# This script will cycle a Flux Bulb Bluetooth Low Energy light bulb
# through a rainbow of different hues if no options are specified.
# It will also change the color of the bulb to a specified color
# or change the brightness of the warm-white LEDs (see --help option).
#
# Dependencies:
# - You must install the pexpect library, typically with 'sudo pip install pexpect'.
# - You must have bluez installed and gatttool in your path (copy it from the
#   attrib directory after building bluez into the /usr/bin/ location).
#
# License: Released under an MIT license: http://opensource.org/licenses/MIT
import colorsys
import math
import sys
import time
import argparse
import re

import pexpect

# Parse input range for hue values
def parseNumRange(string):
    m = re.match(r'(\d+\.?\d*)(?:-(\d+\.?\d*))?$', string)
    # ^ (or use .split('-'). anyway you like.)
    if not m:
        raise argparse.ArgumentTypeError("'" + string + "' is not a range of numbers. Expected forms like '0-1' or '0.2-0.5'.")
    start = float(m.group(1))
    end = float(m.group(2))
    if start < 0 or start > 1 or end < 0 or end > 1 or end < start:
        raise argparse.ArgumentTypeError("'" + string + "' is not a range of numbers from 0 to 1.")
    return (start, end)

# Parse a color value (-r -g -b options) from 0-1 range to the 0-255 range
def parseColorValue(string):
    try:
        color = float(string)
    except:
        raise argparse.ArgumentTypeError("'" + string + "' is not a number.")
    color255 = int(color*255)
    if color255 > 255 or color255 < 0:
        raise argparse.ArgumentTypeError("'" + string + "' is not between 0 and 1")
    colorhex = hex(color255)
    return color255

# Parse an RGB value (-c option) into a list of (r, g, b) values (each 0-255)
def parseRGB(string):
    r,g,b = string.split(',')
    r = parseColorValue(r)
    g = parseColorValue(g)
    b = parseColorValue(b)
    return (r, g, b)

# This checks the hex input of the -x/--rgbhex option and simply returns the input if valid
def parseRGBhex(string):
    m = re.match(r'^(.{2})(.{2})(.{2})$', string)
    if not m:
        raise argparse.ArgumentTypeError("'" + string + "' is not a 3-byte hex string like 00eeff.")
    try:
        r = int(m.group(1),16)
        g = int(m.group(2),16)
        b = int(m.group(3),16)
    except:
        raise argparse.ArgumentTypeError("'" + string + "' is not a 3-byte hex string like 00eeff.")
    return string

# Parse input arguments
parser = argparse.ArgumentParser(description='Control a Flux BLE Bulb')
parser.add_argument('mac',help='Bluetooth MAC address in format xx:xx:xx:xx:xx:xx',
	type=str)
parser.add_argument('-e','--huerange',help='hue range (between 0.0 and 1.0) in format 0.0-1.0',type=parseNumRange)
parser.add_argument('-c','--color',help='change to color given by RGB list, like ' + "'0.5, 0.5, 0.5' (overrides -r -g -b)",metavar='R,G,B',type=parseRGB)
parser.add_argument('-r','--red',help='red value from 0 to 1',type=parseColorValue,metavar='R')
parser.add_argument('-g','--green',help='green value from 0 to 1',type=parseColorValue,metavar='G')
parser.add_argument('-b','--blue',help='blue value from 0 to 1',type=parseColorValue,metavar='B')
parser.add_argument('-w','--white',help='white value from 0 to 1',type=parseColorValue,metavar='W')
parser.add_argument('-a','--addmode',help='''switch addmode on or off. 
            If a color is not specified, the current value in the bulb will remain the same.''',action="store_true")
parser.add_argument('-x','--rgbhex',help='specify RGB color with hex string (overrides -c -r -g -b)',metavar='RRGGBB',type=parseRGBhex)
args = parser.parse_args()

# Check to see which mode we are in.
# If the RGB values are supplied, we need to send one command
# If the warm-white value is supplied, we need to send a slightly different command
# If we want to send both, we need to send a different command entirely

if (args.red is not None or
    args.green is not None or
    args.blue is not None or
    args.color is not None or
    args.rgbhex is not None):
    setcolor = True
else:
    setcolor = False

if args.white is not None:
    setwhite = True
else:
    setwhite = False

if (setwhite and setcolor) or args.addmode:
    setmode = 3
elif setwhite and not setcolor:
    setmode = 2
elif (not setwhite) and setcolor:
    setmode = 1
else:
    setmode = 0

# Configuration values.
if args.huerange is not None:
    HUE_RANGE = args.huerange
else:
    HUE_RANGE  = (0.0, 1.0)
			# Tuple with the minimum and maximum hue values for a
                         # cycle. Stick with 0 to 1 to cover all hues.
SATURATION = 1.0         # Color saturation for hues (1 is full color).
VALUE      = 1.0         # Color value for hues (1 is full value).
CYCLE_SEC  = 20.0         # Amount of time for a full cycle of hues to complete.
SLEEP_SEC  = 0.01        # Amount of time to sleep between loop iterations.


# Get bulb address from command parameters.
#if len(sys.argv) < 2:
#    print 'Error must specify bulb address as parameter!'
#    print 'Usage: sudo python colorific.py <bulb address>'
#    print 'Example: sudo python colorific.py 5C:31:3E:F2:16:13'
#    sys.exit(1)
#if len(sys.argv) = 3:
#bulb = sys.argv[1]
bulb = args.mac
# Run gatttool interactively.
gatt = pexpect.spawn('gatttool -I')

# Connect to the device.
gatt.sendline('connect {0}'.format(bulb))
gatt.expect('Connection successful')

# Setup range of hue value and start at minimum hue.
hue_min, hue_max = HUE_RANGE
hue = hue_min

# Check if we are setting the color manually or running the loop
# setmode = 0 --> loop through hues
# setmode = 1 --> set color only
# setmode = 2 --> set white only
# setmode = 3 --> set both warm-white and color

# set color
if setmode == 1:
    if args.red is not None:
        r = args.red
    else:
        r = 0
    if args.green is not None:
        g = args.green
    else:
        g = 0
    if args.blue is not None:
        b = args.blue
    else:
        b = 0
    if args.color is not None:
        r, g, b = args.color
    if args.rgbhex is None:
        line = 'char-write-cmd 0x002e 56{0:02X}{1:02X}{2:02X}00f0aa'.format(r, g, b)
    else:
        line = 'char-write-cmd 0x002e 56{0}00f0aa'.format(args.rgbhex)
    print line
    gatt.sendline(line)
    time.sleep(SLEEP_SEC)
    gatt.sendline('disconnect')

# set warm-white
elif setmode == 2:
    w = args.white
    line = 'char-write-cmd 0x002e 56000000{0:02X}0faa'.format(w)
    print line
    gatt.sendline(line)
    time.sleep(SLEEP_SEC)
    gatt.sendline('disconnect')

# set colors and warm-white by writing to their respective characteristics
elif setmode == 3:
# Characteristic handles for each color + warm-white
    cmds = {'red': '0x0025',
            'green': '0x0028',
            'blue': '0x002b',
            'white': '0x0031'};
    colors = dict()
    if args.red is not None:
        colors['red'] = args.red
    elif not args.addmode:
        colors['red'] = 0
    if args.green is not None:
        colors['green'] = args.green
    elif not args.addmode:
        colors['green'] = 0
    if args.blue is not None:
        colors['blue'] = args.blue
    elif not args.addmode:
        colors['blue'] = 0
    if args.white is not None:
        colors['white'] = args.white
    elif not args.addmode:
        colors['white'] = 0
    if args.color is not None:
        r, g, b = args.color
        colors['red'] = r
        colors['blue'] = b
        colors['green'] = g
    if args.rgbhex is not None:
        m = re.match(r'^(.{2})(.{2})(.{2})$', args.rgbhex)
        colors['red'] = int(m.group(1),16)
        colors['green'] = int(m.group(2),16)
        colors['blue'] = int(m.group(3),16)
    for key in colors:
        line = 'char-write-cmd {0} {1:02X}'.format(cmds[key], colors[key])
        print line
        gatt.sendline(line)
        time.sleep(SLEEP_SEC)
    time.sleep(SLEEP_SEC)
    gatt.sendline('disconnect')

# Loop through colors
elif setmode == 0:
    # Run main loop
    print 'Press Ctrl-C to quit.'
    last = time.time()
    try:
        while True:
	    # Get amount of time elapsed since last update, then compute hue delta.
            now = time.time()
            hue_delta = (now-last)/CYCLE_SEC*(hue_max-hue_min)
            hue += hue_delta
            # If hue exceeds the maximum wrap back around to start from the minimum.
            if hue > hue_max:
                hue = hue_min+math.modf(hue)[0]
                # Compute 24-bit RGB color based on HSV values.
            r, g, b = map(lambda x: int(x*255.0), colorsys.hsv_to_rgb(hue, SATURATION, 
                                        VALUE))
            # Set light color by sending color change packet over BLE.
            # 56RRGGBB00f0aa
            # If the RGB options are specified, change the light to the specified color
            line = 'char-write-cmd 0x002e 56{0:02X}{1:02X}{2:02X}00f0aa'.format(r, g, b)
            print line
            gatt.sendline(line)
            # Wait a short period of time and setup for the next loop iteration.
            time.sleep(SLEEP_SEC)
            last = now
    except KeyboardInterrupt:
        # turn off the light and disconnect on exit
        line = 'char-write-cmd 0x002e 5600000000f0aa'
        time.sleep(SLEEP_SEC)
        gatt.sendline(line)
        time.sleep(SLEEP_SEC)
        gatt.sendline('disconnect')
