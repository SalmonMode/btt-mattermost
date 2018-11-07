# btt-mattermost

A basic TouchBar utility for Mattermost mentions.

What it does
------------
This shows the numbers of unread mentions for you on a Mattermost server, and launches/brings into focus the Mattermost app
when tapped.

Here's what it looks like with no mentions:

![No Mentions][1]

And here it is with some mentions:

![2 Mentions][2]

How it does it
--------------

This utilizes a ``LaunchAgent`` that handles a websocket connection to a Mattermost server, and uses a SQLite database to
track mention totals for each channel (private chat groups and DMs each count as their own channels as well). The websocket
connection receives every event that your user is allowed to see, but the daemon only cares about mentions and channel views.
As a mention comes in, it increments the number of mentions for that channel, and as you view a channel, it sets the number of
mentions to 0 for that channel. The BTT script just connects to the SQLite DB and totals up all mentions for all channels and
spits it out for the button in the TouchBar to display.

Requirements
------------

  * Mattermost app (``brew cask install mattermost``) (not required if you don't want the tap functionality to launch/switch to the app)
  * Python 3.5+
  * python-daemon (``pip3 install python-daemon``)
  * mattermostdriver (``pip3 install mattermostdriver``)

How to setup it up
------------------

  * Download and install [BetterTouchTool](https://www.boastr.net)
  * Download [config file](btt-mattermost-config.json)
  * Import the configuration file into BetterTouchTool and swap out the "Launch Path" for the location of your Python executable
  * Add the [plist file](com.example.mattermost.plist) to your ``~/Library/LaunchAgents`` folder (I would swap out ``example`` with your username though, both in the file name and in the file itself)
  * Add the [daemon script](mattermost_daemon.py) to your ``~/Scripts/`` folder
  * Add a ``config.ini`` file matching the stricture of the [example config](example_config.ini) to ``/etc/mattermost_daemon/``, but with your own info
  
This may require a restart in order to trigger the plist file to be launched properly, but it should also be able to be started by running ``launchctl start com.example.mattermost``
  
  
[1]: https://raw.github.com/SalmonMode/btt-mattermost/master/screenshots/no_mentions.png
[2]: https://raw.github.com/SalmonMode/btt-mattermost/master/screenshots/2_mentions.png
