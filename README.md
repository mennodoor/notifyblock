# Simple notification daemon for i3blocks

## Overview

This script is a simple notification daemon intended to be used in combination with i3blocks. Its main feature is the ability to mute it and get the missed notifications displayed when unmuting it. Kind of like the focus mode on phones. Also it integrates well in the i3blocks bar.

## Install

Normal location for i3 / i3blocks scripts is here:

```~/.config/i3/scripts/notifyblock.py```

Don't forget to make it executable:

```chmod +x ~/.config/i3/scripts/notifyblock.py```

The following dependencies are required:

```
pip install python-dbus PyGObject
```

## Configuration

You can customize the script's behavior by modifying the following parameters in the code:

- `NOTIFYFORMAT`: Format string for notification display.
- `DEFAULT_TIMEOUT`: Default time a notification will be displayed before being removed.
- `STRING_LENGTH`: Maximum length of the notification body text to be printed. If longer, it shows a running text according to the next three configuration values.
- `STRING_SHIFT`: Number of characters to shift in the running text display.
- `SHIFT_COUNTER`: Number of calls until the text shifted in the running text display.
- `DOUBLE_TIME`: Double the display cooldown in the running text display.

### Command Line Arguments

Its a single script for everything and for the specific tasks, command line arguments have to be given:

- `--daemon`: Runs the daemon to capture and store notifications. (should be called on startup/i3-config)
- `--display`: Formats and prints the notifications based on the current configuration. (called in i3block)
- `--mutetoggle`: Toggles the mute status of notifications. Muted, no notifications displayed, but stored and then displayed when unmuted. (called in i3block)
- `--next`: Removes the first notification from the list, allowing the next one to be displayed. (called in i3block)

### Example i3 and i3blocks config elements:

```bash

# i3block notifications
exec_always --no-startup-id killall notifyblock.py 
exec_always --no-startup-id sleep 2 && ~/.config/i3/scripts/notifyblock.py --daemon

```

```bash

[notifyblock]
label=📨
command=~/.config/i3/scripts/notifyblock.py --display
interval=1
align=left

[notifyblocknext]
full_text=⏭
command=~/.config/i3/scripts/notifyblock.py --next
align=left

[notifyblockmute]
full_text=🔔
command=~/.config/i3/scripts/notifyblock.py --mutetoggle
align=left

```

## License

This project is licensed under the [GNU General Public License v3.0 (GPL-3.0)](https://www.gnu.org/licenses/gpl-3.0.html). See the [LICENSE](./LICENSE) file for details.

Copyright (C) 2024 Menno Door.

## TODO

- Thunderbird issue: Thunderbird refuses to send notifications via dbus, at least on my system.
- Prioritize notifications based on urgency.
- Identify and handle obsolete notifications:
  1. When the same notification is sent multiple times.
  2. When an application sends multiple notifications, making older ones irrelevant.
- Colorize output based on urgency? Other fancy coloring/formating features?
