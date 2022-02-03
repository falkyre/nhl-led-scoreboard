# SBEvents - Event manager for NHL LED Scoreboard

This module will provide an event manager for score board events.  This will include the ability to subscribe and publish to MQTT server, run unix scripts for events, etc.  The event manager will utilize Python Queues and threads to minimize the impact on the core scoreboard system.  

The events that will be handled are as follows (similar to the MQTT events):

# Control Events
These are provided by the CLI or by an MQTT topic that the scoreboard will subscribe to on an MQTT server

* showboard - **display a board**
* brightness - **set brightness from 1-100**
* screensaver - **screensaver on or off**
* datafeed - **pause weather or other data feeds**
* shutdown - **shutdown the scoreboard and raspberry pi**
* pushbutton - **simulate pushbutton events - short/long pushes**
* test - **test adding event to a queue, test goal or test penalty**

# Game Events
These are events that come from the scoreboard during a game

* goal - **goals for home and away team when goal scored - pre and post as well**
* penalty **penalty home/away pre and post as well**
* status **live, intermission, OT, final**

# Non Game Events
These are events that come from the scoreboard not during a game

* status - **game day, off day, off season. pre-game**

# Event Handlers
These are what currently can be used to handle the events.  
* MQTT - control and all other events
* Unix Scripts - all events other than control
* Command Line Interface (telnet) - control only
* WLED - send goal/penalty event to LED via it's JSON API 


With scripts, the event manager will do it's best to handle the script in a safe manner but will not do any types of checks.  There will be the ability to have a script be killed after a period of time.  Also, the main script upon shutdown will kill all child scripts so no zombie processes are created.


