
# NHL-LED-scoreboard

![scoreboard demo](assets/images/scoreboard.jpg)

# Releases

Click on button to go to release notes.

| Latest Stable | Latest nhl_setup |
| --- | --- |
|[![GitHub release (latest by date)](https://img.shields.io/github/v/release/falkyre/nhl-led-scoreboard?sort=date&display_name=release&cacheSeconds=600)](https://github.com/falkyre/nhl-led-scoreboard/releases/latest)|[![GitHub release (latest by date)](https://img.shields.io/github/v/release/falkyre/nhl-setup?sort=date&display_name=release&cacheSeconds=600)](https://github.com/falkyre/nhl-setup/releases/latest) |

# NHL LED Scoreboard Raspberry Pi Image 

[![Create Release - Image](https://github.com/falkyre/nhl-led-scoreboard-img/actions/workflows/main.yml/badge.svg)](https://github.com/falkyre/nhl-led-scoreboard-img/actions/workflows/main.yml)
[![GitHub release (latest by date)](https://badgers.space/github/release/falkyre/nhl-led-scoreboard-img?label=Version)](https://github.com/falkyre/nhl-led-scoreboard-img/releases/latest)

[![discord button](assets/images/discord_button.png)](https://discord.gg/CWa5CzK)
# IMPORTANT (PLEASE READ)
## No seriously, really read the next lines
> [!WARNING]
> I mean it, don't say I didn't warn you

# HARD REQUIREMENTS
## Only Supported Raspberry Pi Hardware
* Raspberry Pi Zero 2w
* Raspberry Pi 3A+, 3B
* Raspberry Pi 4
* Raspberry Pi 5 (experimental and best with 128x64 boards)
## Only Supported RGB Adapters
* Adafruit RGB Bonnet or HAT
* Adafruit Triple LED Matrix Bonnet
* [Electrodragon RGB Matrix Panel Drive board](https://www.electrodragon.com/product/rgb-matrix-panel-drive-board-for-raspberry-pi-v2/)
## Only Supported OS (these have been tested)
* rpi OS Bookworm (32 bit only, 64 bit not tested) or higher (Trixie 32 bit or 64 bit) - **lite version only**
> [!NOTE]
> If you get a segmentation fault on using apt to install packages, reboot your pi and try again.  There maybe some locked files
* Dietpi V9.9.0 or higher (dietpi V9.17.2 is Debian trixie and the board has been tested under this OS)
> [!NOTE]
> Make sure when you setup your dietpi installation for the first time, change this setting in the /boot/dietpi.txt:
> AUTO_UNMASK_LOGIND=0 to AUTO_UNMASK_LOGIND=1
> This makes sure that the systemd-logind is running which provides dbus. 
> Or run sudo systemctl unmask systemd-logind.service if you didn't put that in your original setup

## Only supported Python
* Python 3.11 or higher
* Running in a virtual environment


# Required skills for hardware installation
[Skills needed](#skill-requirements-please-read)

# Installation
The following makes the assumption that you are comfortable with a Linux terminal and command line and the ability to use git.  You are also expected to know how to edit a json file to create a config.json. 
> [!NOTE]
> The _nhl_setup_ binary has been removed from this repository and into it's own.  It has been updated to allow for selecion of Mammoth as a team and there are also now 2 binarries, a 32 bit and 64 bit.  The install.sh will download the proper version for the OS you are running.  Although a little dated, the configuration items in config.json are listed here:  https://github.com/riffnshred/nhl-led-scoreboard/wiki/Configuration

## Clean Install
1. Read the release notes of the release you are installing.  There can be information on breaking changes or procedures that are needed for the release.
2. Install git on your fresh OS.  `sudo apt install git -y`
3. Clone this repository with git :  `git clone --depth 1 https://github.com/falkyre/nhl-led-scoreboard.git` for only latest version (quickest way to clone but you don't get any other branches)
4. Change to the nhl-led-scoreboard directory
5. Run the scripts/install.sh script.  Pay attention to it's output as there is critical information if there are any errors.
6. If the install.sh script has no failures, you can try the samples to see if your board works.  If the samples don't work, the scoreboard code won't either.  
   
> [!NOTE]
> Under Debian 13 Trxie, you will get this error from the install script.  It can be safely ignored

`ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
types-requests 2.32 requires urllib3>=2, but you have urllib3 1.26.20 which is incompatible.
types-docker 7.1 requires urllib3>=2, but you have urllib3 1.26.20 which is incompatible.
types-influxdb-client 1.45 requires urllib3>=2, but you have urllib3 1.26.20 which is incompatible.`

## To run the sample code 
The commands below will show you which python to use, how to run a sample code that is included with the matrix submodule.  The --led* options are specific to this one board so you will need to adjust them accordingly.

```
rpi@nhl-led-scoreboard-office:~ $ cd nhl-led-scoreboard/
(nhlsb-venv) rpi@nhl-led-scoreboard-office:~/nhl-led-scoreboard $ which python
/home/rpi/nhlsb-venv/bin/python
(nhlsb-venv) rpi@nhl-led-scoreboard-office:~/nhl-led-scoreboard $ cd submodules/matrix/bindings/python/samples/
(nhlsb-venv) rpi@nhl-led-scoreboard-office:~/nhl-led-scoreboard/submodules/matrix/bindings/python/samples $ sudo env "PATH=$PATH" python runtext.py --led-gpio-mapping=adafruit-hat-pwm --led-brightness=60 --led-slowdown-gpio=3 --led-rgb-sequence=rgb --led-rows=64 --led-cols=128 --led-pwm-bits=10
Press CTRL-C to stop sample
```


   
## Upgrade
>[!CAUTION]
> You can only upgrade over top of this repository's code. If you are running someone else's fork, or the original nhl-led-scoreboard, you will not be able to upgrade.  You will quickly run into some very obvious pain points.

The scripts/install.sh will offer a new install or upgrade.  It should work on an upgrade **unless you are directed to do a _clean install_ in the release notes (see point 1 of clean install)**

## Directed to do clean install
1. Make a copy of your config.json file.
2. Delete the /home/pi/nhlsb_venv folder
3. Delete the /home/pi/nhl-led-scoreboard folder
4. Follow the steps for a clean install
  
**OR - if you want really clean install:**

1. Make a copy of your config.json file to local computer
2. Download OS of choice (32 or 64 bit raspiOS), set that up
3. Follow steps for clean install

## Random notes on the install
Some of the python libraries that we are using are created using an older method of packing.  As a result, you may see warnings in the output of the install.sh script similar to this:

`DEPRECATION: Wheel filename 'regex-2013_12_31-cp37-cp37m-linux_armv6l.whl' is not correctly normalised. Future versions of pip will raise the following error:
  Invalid wheel filename (invalid version): 'regex-2013_12_31-cp37-cp37m-linux_armv6l'`

These warnings can be ignored.

# Troubleshooting
**Rule #1:  W.A.E.F.R.T.F.M ---> read the readme again**

If you need help, there is a Discord that still runs.  See above for the link.  However, please be prepared with some information other than a generic, my board has crashed.  There is a script in the scripts/sbtools folder called issueUpload.sh.  This will gather information from your installation and paste it to a pastebin.  Plewse do that and provide the pastebin link that the script gives you.  Also, ensure that you have read the latest release notes in case there is something there you have missed.

>[!IMPORTANT]
> The NHL API, which drives the data for the scoreboard is unofficially publically available and can be unreliable at times.  We have no control over it nor if it will still remain open to the public.  We joke that the NHL Interns are breaking it when things go wrong, but who knows?  We were blind sided in 2023 when the NHL switched to a new API.  It's great that the community came together and mapped out the new version.


<details>
<summary>Old Readme sections, read if you want some history</summary>

## (2025-07-08) We now have an image and some Mammoth team names.
Effective release 2025.7.0, the minimum supported version of Python is 3.11.  If you run the latest rpiOS built on Debian Bookworm, you are ok.  Anything lower than Python 3.11, the install script WILL NOT COMPLETE with the proper Python libraries required to run the scoreboard.

I've switched over to using CALVER(https://calver.org/) versioning.  This will follow the YYYY.MM.minor numbering scheme.  So anything released n March of 2025 will have a 2025.3.x version number.  I've done this to step away from the old versioning and not keep updating the last V1.9.xxxxxx.

As of 2025.3.0, you can now download and run the scoreboard in a web browser using docker or podman.  The images are published here:  https://github.com/falkyre/nhl-led-scoreboard/pkgs/container/nhl-led-scoreboard and are two platforms (linux/amd64 or linux/arm64).  This is completely seperate from running the scoreboard on physical hardware and is just another way to enjoy this tremendous application.  The docker-compose.yml file will create a container with the code in this repository and run a webserver on port 8888 that will display the scoreboard.  If you don't run the docker-compose up from where you downloaded this repository, you'll have to change the ./config/config.json line in the docker-compose file to point to where you locally have a config.json file.  Change the TZ environment variable to reflect your timezone.  You can change the ports to use a different host based port if you want to (the format is host port:container port).  Don't change the container port number from 8888.

## (2025-01-10) It's ALIVE ... All hail V1.9.0 ... for now
This version of the NHL LED Scoreboard has been updated to work with the latest changes to the NHL API along with other additions that were planned for the next release.  This includes MQTT, a change to remove pyowm library as the OWM API it used has been deprecated.  Also, removed the use of the geocoder library as it was failing on doing a location lookup.  This release also adds the RGB Emulator code so you can also run the Web version of the NHL LED Scoreboard if you want to (use the --emulated command line)

## (2024-05-17) THE END ... For now...
After what seems to be some minor change in the NHL API, new issues arose which rendered the software unusable. I have been working on a new version built from the ground up and decided to put my focus on it instead of fixing and supporting this one. I therefore decided to Archive this repository. The plan is to roll out the new version in the fall, in time for the 2024-2025 NHL season.

## (2023-11-09)
old stats api is officially dead. please read below on the current state of the project. only thing that change is that the plan is that Ill start from scratch for the next version. No time frame on anything for now for reasons stated below

## (2023-10-11) Indefinitly on Hold. More changes and complications. Limited free time. Future uncertain (Don't build this for a friend).
Over the last few weeks, we discovered that the NHL API has changed to a new one and the previous version is now unreliable (even tho it came back to life after being out for a few days). More so, a lot of packages, plugins and more recently, the OS we use had a major update and the software stack we use to make this project work changed a lot. This means that the current documentation of this project is now partially deprecated. If you have enough know-how, you can make the project work. Due to unforeseen events in my life, I no longer have the same amount of free time to dedicate to this project, keep it up to date and make it easy to use. 

The current situation is, that if you have a working scoreboard, it should be fine while the previous NHL API is operational. If your scoreboard is not working at the moment, you may try the image version of the scoreboard offered by Falkyre. He's currently working on fixing a few things related to software changes and OS changes, but I believe he will have it up and running in the coming days. Again, this uses the previous version of the NHL API and thus, its fate is the same. 

What I'm focusing on with the little time I find is fixing the code of this project to use the new NHL API. This will take a bit of time. 


## Compatible Raspberry pi OS
V1.9.0 has been tested and used on the latest bookworm from Raspberry Pi (November 2024) as well as DietPi V9.9.0 (based on bookworm).
For v1.6.x and lower, use Raspberry Pi OS Lite (Legacy). The newer version of Raspberry pi OS (Bullseye) is not supported at the moment.  


### Supported Raspberry Pi models

The models we support are the Raspberry Pi Zero 2W, all the Raspberry pi 3 and the Pi 4 models. 

If you are looking to replace your raspberry pi Zero, I personally recommend the Raspberry pi 3A+. If you use the RGB Bonnet along with that, make sure to isolate the bottom of it with a few layers of Kapton tape or a layer of electrical tape.

## Description

This is a Python software made to display NHL live scores, stats, and more of your favorite teams, on a Raspberry Pi driven RGB LED matrix. An LED matrix panel (also called a Dot led matrix or dot matrix) is a panel of LEDs used to build huge displays as you see in arenas, malls, time square, etc...

## Skill requirements (PLEASE READ)
I reckon that a lot of interest come from users that have little to no experience with a raspberry pi or computers and how to set up and use electronic devices in general. To help yourself here are some basic skills you need in order to set up and use this software and the device you are about to build. 

* Basic knowledge of Bash command language and terminal navigation. Here is a starting point https://www.raspberrypi.org/documentation/linux/usage/commands.md
* Basic Knowledge of Electronics. 
* Willingness to fail and keep trying.
* (Optional but recommended) Basic soldering skill. 

This documentation offers technical information related to the installation and execution of this software only. You will need to figure out other unrelated technical processes through tutorials or searching on google.


## Disclaimer

This project relies on an undocumented NHL API which is also what nhl.com use. The data is not always accurate and might have delays and errors that's out of our control.

  

## Tutorials from other source

>"I followed instructions from somewhere else and I'm having issues"

  

This project is new and is in constant evolution. Please read the documentation and instructions to install and run this software provided here.

  

## Support and community

<a  href="assets/images/community_4.jpg"  target="_blank"><img  width="115"  src="assets/images/community_4.jpg"></a> <a  href="assets/images/community_2.jpg"  target="_blank"> <img  width="220"  src="assets/images/community_2.jpg"></a><a  href="assets/images/community_1.jpg"  target="_blank"> <img  width="220"  src="assets/images/community_1.jpg"></a> <a  href="assets/images/community_3.jpg"  target="_blank"> <img  width="220"  src="assets/images/community_3.jpg"></a>

**NEW on MARCH 2 2020***
The Discord Channel still exist, But We now use the new [Discussions](https://github.com/riffnshred/nhl-led-scoreboard/discussions) section. If you need help, are looking for resources, show off your setup or want to keep up with what's going on with the project, this is where it's all about.

## Requirements

Installation in a python virtual enviroment is now the preferred way of installation due to the upcoming Raspberry Pi OS Bookworm and Python 3.11.  The install.sh script will handle this for you (the venv will be installed in the directory ``nhlsb_venv`` in the home directory of the user doing the install).  This will change how the scoreboard is launched as you now need to reference the venv python and not the global python install. 

**Previous way with everything globally install as root user**

> `sudo python3 ./src/main.py [command line options]`

**Now with the venv**
> `sudo /home/pi/nhlsb-venv/bin/python3 ./src/main.py [command line options]`

Since version V1.0.0 you need python 3.3 and up.


## Time and data accuracy
The scoreboard refreshes the data at a faster rate (15 seconds by default, don't go faster than 10). This does not change the fact that the data from the API is refreshed every minute. The faster refresh rate allows catching the new data from the API faster.

Syncing the scoreboard with a TV Broadcast is, to my knowledge, impossible. The delay between the actual game and the TV broadcast is different depending on where you are in relation to the game's location. This also means that you will see the goal animation before it happens on TV sometimes. I'm working on this issue and looking to find a solution to implement a delay at some point. 

Also, it might happen the data shown on board might be wrong for a short time, even goals. That is because the API is drunk. If you see data that might be wrong, compare it to the nhl.com and see if it's different.


## Hardware and Assembly
Please refer to the [Hardware page](https://github.com/riffnshred/nhl-led-scoreboard/wiki/Hardware) in the wiki section. You will find everything you need to order and build your scoreboard.  

**IMPORTANT NOTE**: Even tho there are other ways to run an rgb led matrix, I only support for the Adafruit HAT and Adafruit Bonnet. They have a great tutorial on how to install both of them on their website. Follow these steps until **STEP 5** to assemble your setup. https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi/driving-matrices

If you create an issue because you are having trouble running your setup and you are using something different, I will close it and tell you to buy the appropriate parts or to check the [rpi-rgb-led-matrix ](https://github.com/hzeller/rpi-rgb-led-matrix) repo.


## Software Installation

### Method 1 - Using the nhl-led-scoreboard-img (Recommended)
You can now install, connect, configure and run the scoreboard using the new [nhl-led-scoreboard-img](https://github.com/falkyre/nhl-led-scoreboard-img)
PLEASE READ THE DOCUMENTATION AND TAKE YOUR TIME TO GO THROUGH THE PROCESS.
**NOTE**: This image has been tested but is still in Beta. If you have issues, Open a new issue on His repository. 

Download the image [HERE](https://github.com/falkyre/nhl-led-scoreboard-img/releases)


**Note that this images is generated AFTER I release a new update. keep an eye on the Badges at the top of the page or on the repository it self to see when the new image comes out**

### Method 2 - Standard installation and setup (For Dev and Modders).
This is the classic way to install and configure the scoreboard. If you want to do your own thing and add or modify components to your scoreboard, I recommend fallowing this guide to install, configure and run your scoreboard. 

[Step by step installation guide](https://github.com/riffnshred/nhl-led-scoreboard/wiki/Step-by-step-guide.)

### Method 3 - Software Emulation
You can install the software to run in an emulated mode via a variety of display adapters by using [RGBMatrixEmulator](https://github.com/ty-porter/RGBMatrixEmulator).

Installation is straight-forward using the emulator installer script appropriate for your operating system:

MacOS / Linux:

```sh
sh scripts/emulator_setup.sh
```

Windows:

```sh
TODO
```

Once your emulated software is installed, you can continue with [Step 5 of the manual setup guide].

Running the emulated version of the board is easy:

```sh
python3 src/main.py --emulated
```

See [RGBMatrixEmulator customization options] for further customization of the display.
 

## Shout-out

First, these two for making this repo top notch and already working on future versions:

- [Josh Kay](https://github.com/joshkay)

- [Sean Ostermann](https://github.com/falkyre)

This project was inspired by the [mlb-led-scoreboard](https://github.com/MLB-LED-Scoreboard/mlb-led-scoreboard). Go check it out and try it on your board, even if you are not a baseball fan, it's amazing.

I also used this [nhlscoreboard repo](https://github.com/quarterturn/nhlscoreboard) as a guide at the very beginning as I was learning python.
You all can thank [Drew Hynes](https://gitlab.com/dword4) for his hard work on documenting the free [nhl api](https://gitlab.com/dword4/nhlapi).

## Licensing

This project uses the GNU Public License. If you intend to sell these, the code must remain open source.
</details>
