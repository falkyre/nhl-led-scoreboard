How to on SteamDeck:

Install distrobox : https://github.com/89luca89/distrobox/blob/main/docs/posts/install_rootless.md
Once distrobox is installed:

Create a debian distro:

[16:52:34] deck@steamdeck /home/deck
> distrobox create debian:11                                                                                                                                         16:52:34
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
Creating 'debian:11' using image registry.fedoraproject.org/fedora-toolbox:36	Error: error running container create option: names must match [a-zA-Z0-9][a-zA-Z0-9_.-]*: invalid argument
 [ ERR ]
[16:56:33] deck@steamdeck /home/deck
> distrobox create -i debian:11                                                                                                                                      16:56:33
Image debian:11 not found.
Do you want to pull the image now? [Y/n]: y
✔ docker.io/library/debian:11
Trying to pull docker.io/library/debian:11...
Error: initializing source docker://debian:11: pinging container registry registry-1.docker.io: Get "https://registry-1.docker.io/v2/": dial tcp: lookup registry-1.docker.io: Try again

An error occurred

An error occurred
[16:57:46] deck@steamdeck /home/deck [125]
> distrobox create -i debian                                                                                                                                         16:57:46
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

Notice that the prmpt is the same as the steamdeck prompt but now has the name of the distro you created

To exit, logout or CTRL-D or exit, like you normally would to logout of an SSH session

To enter:

distrobox enter <distroname>

eg:  distrobox enter debian

To get scoreboard working:

Install required packages: 
sudo apt install git build-essential python3-setuptools python3-dev python3-cairosvg python3-numpy python3-venv python3-sdl2

Clone https://github.com/falkyre/nhl-led-scoreboard.git
cd to where you cloned it
git checkout emulator-flatpak

Create a virtual enviroment

python3 -m venv venv

Activate your virtual environment

source venv/bin/activate

Install pip requirements using the emulator_requirements.txt:
pip3 install -r emulator_requirements.txt

Create your  config.json

Run your scoreboard (from the root of where you cloned it).  No need for sudo as we don't need hardware access

python3 src/main.py --emulated

This will start the browser adapter, go to http://<ip address of steamdeck>:8888 to see

Stop the code

Edit the emulator_config.json and change browser to pygame
