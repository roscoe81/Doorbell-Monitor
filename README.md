# Doorbell-Monitor
Provides doorbell automation for a Fermax 4 + N Electronic Door Entry System 
This project uses a Raspberry Pi to:
a) Auto Mode: Play a recoded message and open the door so that deliveries can be left in a secure location
b) Manual Mode: Places a Video SIP call to your mobile phone so that you can see the person at the door and converse with them
c) Idle Mode: Normal door station functions take place
In all modes, a photo of the caller is taken and stored for later reference. There is also the option to only allow Auto mode during certain hours of yteh day and days of the week.
In addition to the mode setting buttons and indicators, an mqtt interface is provided to allow remote mode setting and to open the doo manually.
A separate project (Home Manager) utilises that mqtt interface as part of a broader home automation project and will be published at a later date.

Interfacing
Images of the interface schematics are included in this repository, as are a few photographs of the hardware during various phases of repackaging.
