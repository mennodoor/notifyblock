#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
### notifyblock - A simple notification system that can be used in combination with i3blocks. 
#
# notifyblock is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# notifyblock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with notifyblock. If not, see <https://www.gnu.org/licenses/>.
#
# Author: Menno Door <mdoor+notifyblock@posteo.de>
# Copyright (C) 2024 Menno Door


### TODO
# - prioritise notifications based on urgency
# - identify and handle obsolete notifications: 1) When the same notification is sent multiple times or 2) the
#   same application sends multiple notifications and makes older ones irrelevant.
# - colorise the output based on urgency? 
# - maybe move the configuration to a configuration file (e.g. ~/.config/i3/notifyconf ?)
# - the default /tmp files are probably not the best solution for multi-user systems

### NOTE: functionalities by sys arg:
# - daemon:
#      The actual daemon service. The main() function does a, initialization of the required dbus session and
#      notification class objects and then runs a never ending loop. 
#      The linked Notify() function will accept incoming notifications and will summerize the information in a 
#      dictionary and stores these in a /tmp/ file as json.dumps, each line one notification.
#      This is actually the only thing the daemon does.  
# - display:
#      The function used for formatting and printing notifications. It does a little bit more than that, it 
#      also handles the notification cool downs and cleans up the notifications list in /tmp/.
# - mute_toggle:
#      A simple function to toggle the mute status of the notification display. If muted the notificaitons will
#      not be displayed but they still are stored. When unmuted, the missed notifications will be shown in the
#      order they've been recorded with the respective cool down times. --- This is actually the main functionality
#      I build this for, it is kind of like the focus mode on android phones. --- Calling this function will print
#      also a bell or crossed bell icon to stdout, which can be used in i3blocks as a toggle button.
# - next:
#      This function will remove the first notification from the list, so that the next notification will be displayed.


### NOTE: Configuaration
# config
STRING_LENGTH = 60
STRING_SHIFT = 20
DOUBLE_TIME = True # double the diplay cool down, if the notification is too long
SHIFT_COUNTER = 2 # how many calls until the shift is applied (1 would be every call, 2 every second ...)

DEFAULT_TIMEOUT = 4000
DEBUG = False
#TIMETAGFORMAT = "%Y-%m-%d %H:%M:%S"
TIMETAGFORMAT = "%H:%M:%S"
# available variables: timetag, app_name, summary, body, urgency, rest_time,
#                      sender_pid, app_icon, replaces_id, actions, expire_timeout
NOTIFYFORMAT = "{timetag}/ {app_name}/ {summary} {body}/ {urgency} ({rest_time})"

### imports
import os, json, hashlib
from pathlib import Path
from datetime import datetime

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

#from termcolor import colored

### temporary files
NOTIF_FILE = Path.home() / ".cache" / "notifyblock_list"
MUTE_FILE = Path.home() / ".cache" / "notifyblock_mute_toggle"
LAST_DISPLAY_FILE = Path.home() / ".cache" / "notifyblock_last_display"
# Ensure required files exist
for file in [NOTIF_FILE, MUTE_FILE, LAST_DISPLAY_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            f.write("")


### notification list file IO
def append_notification(infodict):
    # write infodict as a single line of json
    with open(NOTIF_FILE, 'a') as f:
        f.write(json.dumps(infodict) + '\n')

def write_notifications(notificationlist):
    # overwrite the whole file:
    jsonlist = [json.dumps(i) for i in notificationlist]
    if DEBUG:
        print('write notifications', notificationlist)
    with open(NOTIF_FILE, 'w') as f:
        f.write('\n'.join(jsonlist))

def read_notifications():
    # read the notifications back as a list of dicts
    with open(NOTIF_FILE, 'r') as f:
        notifications = f.readlines()
    if DEBUG:
        print('read notifications', notifications)
    if notifications:
        return [json.loads(i.strip()) for i in notifications]
    else:
        return []

### time stamps and hash helper functions
def tstamp_to_dtime(timestamp):
    return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")

def dtime_to_tstamp(dtime, FMT="%Y-%m-%d %H:%M:%S.%f"):
    return dtime.strftime(FMT)

def dtimediffms(dtime1, dtime2):
    return int((dtime1 - dtime2).total_seconds() * 1000)

def hashdict(infodict):
    start = datetime.now()
    if DEBUG: print( json.dumps(infodict) )
    #hashstr =  str(hash(json.dumps(infodict)))
    #hashstr =  str(hashlib.md5((json.dumps(infodict).encode())))
    hashstr =  str(hashlib.md5(json.dumps(infodict).encode('utf-8')).hexdigest())
    end = datetime.now()
    if DEBUG: print('hashing time', end-start, hashstr)
    return hashstr

### last displayed notification
def write_last_display(infodict, counter, first_time=None):
    hashstr = hashdict(infodict)
    if first_time is None:
        first_time = dtime_to_tstamp(datetime.now())
    try:
        first_time = dtime_to_tstamp(first_time)
    except:
        pass
    with open(LAST_DISPLAY_FILE, 'w') as f:
        f.write(first_time + ';' + hashstr + ';' + str(counter))

def read_last_display():
    with open(LAST_DISPLAY_FILE, 'r') as f:
        line = f.read()
    if line:
        timestr, hashstr, counter =  line.split(';')
        dtime = tstamp_to_dtime(timestr)
        if DEBUG: print('read last display', timestr, hashstr, counter)
        return dtime, hashstr, int(counter)
    return None, None, None

### ctrl mute status
def read_mute_status():
    with open(MUTE_FILE, 'r') as f:
        status = f.read().strip() == "True"
    return status

def toggle_mute():
    # toggle the file
    current_status = read_mute_status()
    new_status = "False" if current_status else "True"
    with open(MUTE_FILE, 'w') as f:
        f.write(new_status)
    # also print an appropriate icon, for the i3blocks item
    if new_status == "True":
        print("🔕")
    else:
        print("🔔")

### notification print line
def print_notification(notification, counter, rest_time):

    counter = int(counter / SHIFT_COUNTER)
    
    # get parameters
    timetag = notification['timetag']
    timetag = tstamp_to_dtime(timetag)
    timetag = dtime_to_tstamp(timetag, TIMETAGFORMAT)
    summary = notification['summary']
    body = notification['body']
    sender_pid = notification['sender-pid']
    app_name = notification['app_name']
    app_icon = notification['app_icon']
    replaces_id = notification['replaces_id']
    actions = notification['actions']
    expire_timeout = notification['expire_timeout']
    urgency = notification['urgency']
    urgency = "[" + "!" * urgency + "]"

    # if the body text is too long (config), make it a running text.
    bodylength = len(body)
    if bodylength > STRING_LENGTH:
        body = body + ' - ' + body # to prevent too short text pieces
        position = (STRING_SHIFT*counter)%bodylength # calc curr position
        body = body[position:position+STRING_LENGTH] # take substring

    # build string given the format definition
    string = eval(f"f'{NOTIFYFORMAT}'")
    # strip string of functional characters, e.g. |, \n, \t, <>, etc.
    string = string.replace('\n', ' ').replace('|', ' ').replace('<', ' ').replace('>', ' ')

    print(string)

### called by --display tag, handles the logic and decides what to print
def display_notification():
    # check mute status
    if read_mute_status():
        print('notifications muted')
        return 

    # check for notifications
    notifications = read_notifications()
    if not notifications:
        print("No notifications")
        return

    first = notifications[0]
    #print(first)
    firsthash = hashdict(first) 
    first_timeout = first.get('expire_timeout', DEFAULT_TIMEOUT)
    rest = notifications[1:]

    # get current time and information about the last displayed notification
    current_time = datetime.now()
    last_display_firsttime, last_display_hash, last_display_counter = read_last_display()
    
    # if there is nothing in the last_display file or if the last_display_hash
    # is not the same as the current first notification (because the last one
    # was deleted from the list after its cooldown), the last_display file is
    # updated and the current notification printed
    if last_display_firsttime is None or firsthash != last_display_hash:
        if DEBUG: print('new notification')
        write_last_display(first, counter=0) # the counter is for a running text, it
        print_notification(first, counter=0, rest_time=int(first_timeout/1000)) # just has to be reset here
        return

    # if not, we have to handle the cooldown and potential removal of the current
    # notificiation and update the last_display file and also print the notification
    timediff = 0

    # check if the notification is due to be removed
    timediff = dtimediffms(current_time, last_display_firsttime)
    if timediff > first_timeout:
        if DEBUG: print('over time!')
        # remove the notification by writing the rest
        write_notifications(rest)
        # display the next notification by calling itself
        display_notification()
        return 
    
    if DEBUG: print('reprint!')

    # the notification seems to be still valid, so lets update the counter and 
    # print it
    rest_time = int( (first_timeout - timediff)/1000 )
    if DEBUG: print('rest time', rest_time)
    counter = last_display_counter + 1
    write_last_display(first, counter, last_display_firsttime)
    print_notification(first, counter=counter, rest_time=rest_time)
    return    

### main function, called by --daemon tag
def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    session_bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("org.freedesktop.Notifications", bus=session_bus)
    notification_service = NotificationService(bus_name)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()

### dbus service class
class NotificationService(dbus.service.Object):
    def __init__(self, bus_name):
        dbus.service.Object.__init__(self, bus_name, "/org/freedesktop/Notifications")

    @dbus.service.method("org.freedesktop.Notifications", in_signature='susssasa{sv}i', out_signature='u')
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        if int(expire_timeout) < 0:
            expire_timeout = DEFAULT_TIMEOUT
        
        body = str(body)
        if len(body) > STRING_LENGTH and DOUBLE_TIME:
            expire_timeout = expire_timeout * 2
            
        timetag = dtime_to_tstamp(datetime.now())
        infodict = {
            "timetag": timetag,
            "summary": str(summary),
            "body": body,
            "expire_timeout": int(expire_timeout),
            "app_name": str(app_name),
            "app_icon": str(app_icon),
            "replaces_id": int(replaces_id),
            "actions": list(actions),
            "urgency": int(hints.get("urgency", 1)),
            "sender-pid": int(hints.get("sender-pid", 0))
        }
        
        append_notification(infodict)
        print(f"{timetag}: Received notification: {summary} -- {body} with duration {expire_timeout}")
        return 0

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='as')
    def GetCapabilities(self):
        return ['body']

    @dbus.service.method("org.freedesktop.Notifications", in_signature='', out_signature='ssss')
    def GetServerInformation(self):
        #return ('i3blocks-notify', 'i3blocks', '1.0', '1.2')
        return ('notifyblock', 'notifications', '1.0', '1.2')





if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        if sys.argv[2] == '--debug':
            DEBUG = True

    if len(sys.argv) > 1:
        if sys.argv[1] == '--daemon':
            main()
        elif sys.argv[1] == '--display':
            display_notification()
        elif sys.argv[1] == '--mutetoggle':
            toggle_mute()
        elif sys.argv[1] == '--next':
            notifications = read_notifications()
            if notifications:
                write_notifications(notifications[1:])
        else:
            print('no such service')
   
    else:
        print('no arg, no service')
