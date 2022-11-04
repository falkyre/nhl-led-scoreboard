<h1>How to on SteamDeck</h1>

<h2>Install distrobox</h2> 

***

Follow this guide https://github.com/89luca89/distrobox/blob/main/docs/posts/install_rootless.md

Pay attention to Step 3 specifically as you may need to forward your xhost so the GUI shows up.

Once distrobox is installed, you need to create your first distro.

<h2>Create a debian distro</h2>

***
    [16:52:34] deck@steamdeck /home/deck
    > distrobox create -i debian                                                                                                                                         16:52:34
    Image registry.fedoraproject.org/fedora-toolbox:36 not found.
    Do you want to pull the image now? [Y/n]: y
    Trying to pull registry.fedoraproject.org/fedora-toolbox:36...
    Getting image source signatures
    Copying blob 61082f4917d7 done
    Copying blob 50c82c703913 done
    Copying config 2110dbbc33 done
    Writing manifest to image destination
    Storing signatures
    2110dbbc33d288a81b2c6f8658130f7c6dc46704d32eb13bb5b30f6e24ee6125

    Image debian not found.
    Do you want to pull the image now? [Y/n]: y
    ✔ docker.io/library/debian:latest
    Trying to pull docker.io/library/debian:latest...
    Getting image source signatures
    Copying blob 17c9e6141fdb done
    Copying config d8cacd17cf done
    Writing manifest to image destination
    Storing signatures
    d8cacd17cfdcf44e296b41c96f5dab7ae82024c28c4f45bd9181f3823bca639f
    Creating 'debian' using image debian	 [ OK ]
    Distrobox 'debian' successfully created.
    To enter, run:

    distrobox enter debian

    debian
    [16:58:25] deck@steamdeck /home/deck
    > distrobox enter debian                                                                                                                                             16:58:25
    Container debian is not running.
    Starting container debian
    run this command to follow along:

    podman logs -f debian

    Starting container...                  	 [ OK ]
    Installing basic packages...           	 [ OK ]
    Setting up read-only mounts...         	 [ OK ]
    Setting up read-write mounts...        	 [ OK ]
    Setting up host's sockets integration...	 [ OK ]
    Integrating host's themes, icons, fonts...	 [ OK ]
    Setting up package manager exceptions...	 [ OK ]
    Setting up dpkg exceptions...          	 [ OK ]
    Setting up apt hooks...                	 [ OK ]
    Setting up sudo...                     	 [ OK ]
    Setting up groups...                   	 [ OK ]
    Setting up users...                    	 [ OK ]
    Executing init hooks...                	 [ OK ]

    Container Setup Complete!

    Welcome to fish, the friendly interactive shell
    [17:02:15] deck@debian /home/deck

***

Notice that the prompt is the same as the steamdeck prompt but now has the name of the distro you created.  

**deck@steamdeck** changed to **deck@debian**

You can change this by using the **chsh** command (see https://github.com/89luca89/distrobox/blob/main/docs/useful_tips.md#use-a-different-shell-than-the-host).  This needs to be done each time you restart the distrobox.  

To exit, logout or CTRL-D or exit, like you normally would to logout of an SSH session

<h2>Enter your distrobox</h2>

    distrobox enter <distroname>

eg:  
>distrobox enter debian

***

<h2>To get scoreboard working</h2>

Install required packages: 
>sudo apt install git build-essential python3-setuptools python3-dev python3-cairosvg python3-numpy python3-venv python3-sdl2

Clone https://github.com/falkyre/nhl-led-scoreboard.git

cd to where you cloned it and change to the emulator branch

>git checkout emulator

Create a virtual enviroment

>python3 -m venv venv

Activate your virtual environment

>source venv/bin/activate

Install pip requirements using the emulator_requirements.txt:

>pip3 install -r emulator_requirements.txt

<h2>Create your config.json</h2>
    cd config
    cp config.json.sample config.json

Run your scoreboard (from the root of where you cloned it).  No need for sudo as we don't need hardware access

>python3 src/main.py --emulated

This will start the browser adapter, go to http://<ip address of steamdeck>:8888 to see

Stop the running scoreboard (CTRL-C)

Edit the newley created emulator_config.json and change browser to pygame
