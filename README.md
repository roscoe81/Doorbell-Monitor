# Doorbell-Monitor
Provides doorbell automation for a Fermax 4 + N Electronic Door Entry System 
This project uses a Raspberry Pi to:

* Auto Mode: Play a recoded message when the doorbell is rung and open the door so that deliveries can be left in a secure location
* Manual Mode: Places a Video SIP call to your mobile phone when the doorbell is rung so that you can see the person at the door and converse with them
* Idle Mode: Normal door station functions take place.
In all modes, a photo of the caller is taken and stored for later reference and a pushover message is sent that contains the photo. There is also the option to only allow Auto mode during certain hours of the day and days of the week and to disable auto mode if the apartment's door is open.

In addition to the mode setting buttons and indicators, an mqtt interface is provided to allow remote mode setting and to open the door manually. A separate project ([Home Manager](https://github.com/roscoe81/Home-Manager)) utilises that mqtt interface to control this monitor as part of a broader home automation project.

## Hardware Schematics
### Main Schematic
![Main Schematic](https://github.com/roscoe81/Doorbell-Monitor/blob/master/Schematics%20and%20Photos/Doorbell%202_schem.png)

### Switches and Indicators Schematic
![Switches and Indicators](https://github.com/roscoe81/Doorbell-Monitor/blob/master/Schematics%20and%20Photos/Doorbell%20Switches_Indicators_schem.png)

## Hardware Prototyping and Packaging
### Breadboard
![Breadboard](https://github.com/roscoe81/Doorbell-Monitor/blob/master/Schematics%20and%20Photos/IMG_3064.png)
### Initial Packaging
![Initial Packaging](https://github.com/roscoe81/Doorbell-Monitor/blob/master/Schematics%20and%20Photos/IMG_1352.png)
### Final Packaging
![Final Packaging](https://github.com/roscoe81/Doorbell-Monitor/blob/master/Schematics%20and%20Photos/IMG_3065.png)

## License

This project is licensed under the MIT License - see the LICENSE.md file for details
