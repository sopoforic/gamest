# Gamest

Gamest is a tool for keeping a record of time spent playing video games.

## Installation

Use pip to install gamest:

```
pip install gamest
```

Gamest may be launched by calling `gamest` from the command line. The executable
`gamest.exe` is located in python's `Scripts` folder, so a shortcut may be
placed wherever is convenient.

## Configuration

Out of the box, gamest will track runtime of desired apps. To add an app to be
tracked, start the app, then click 'Pick Game`, choose the app from the list,
and click 'Pick Game' to select it. In most cases, no advanced settings will be
required, so click 'Add Game' to finish adding the app to the database. In the
future, the app will be automatically detected whenever it is running.

Gamest settings are stored in `%LOCALAPPDATA%\gamest\gamest.conf`. The default
configuration is:

```
[options]
# Set debug to True to enable logging of additional debug messages for
# troubleshooting.
#
# debug = False

# Only windows which are visible on the desktop will be shown in the
# 'Pick Games' list. Set visible_only to False if you need to select
# an app which doesn't present a visible window.
#
# visible_only = True
```

Plugins may require additional configuration. Included with gamest is a plugin
to send notification when game sessions begin or end. Its configuration is
located in `%LOCALAPPDATA%\gamest\PlaySessionNotificationPlugin.conf`. The
default configuration is:

```
[PlaySessionNotificationPlugin]
# Send notifications when an app is started. This doesn't do anything
# unless a notification service plugin, such as the discord webhook
# notifier, is installed.
#
# send_begin = True

# Send notifications when an app is closed. This doesn't do anything
# unless a notification service plugin, such as the discord webhook
# notifier, is installed.
#
# send_end = True
```

## License

Copyright (C) 2018  Tracy Poff

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
