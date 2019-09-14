#!/usr/bin/env python3
# Northcliff Doorbell Monitor Version 2.3 GEN
import RPi.GPIO as GPIO
import time
from datetime import datetime
import subprocess
import http.client
import urllib
import mmap
import requests
from threading import Thread
import paho.mqtt.client as mqtt
import struct
import json
import os

class TwoLedFlash(object): # The class for the LED flashing thread
    def __init__(self, cycle_duration, cycle_count):
        self.cycle_duration = cycle_duration
        self.cycle_count = cycle_count
        # Set up the LED GPIO ports
        self.auto_led_off = 21
        self.manual_led_off = 27
        GPIO.setup(self.auto_led_off, GPIO.OUT)
        GPIO.setup(self.manual_led_off, GPIO.OUT)
        # Turn off both LEDs
        GPIO.output(self.manual_led_off, True)
        self.manual_led_state = False
        GPIO.output(self.auto_led_off, True)
        self.auto_led_state = False
        self.manual_led_on_count = 10 # LED flashing during startup
        self.auto_led_on_count = 10 # LED flashing during startup
        self.flash_enable = True # Allows LED flashing to proceed upon startup
        self.led_counter = 0 # Reset LED Counter upon startup
        
    def terminate(self): # Stops the LED flashing loop upon shutdown
        self.flash_enable = False
        
    def run(self): # The LED flashing method
        while self.flash_enable == True: # LED flashing loop continues until shut down
            if self.led_counter < self.cycle_count: # led_cycle count sets the number of loops per cycle
                if self.led_counter >= self.manual_led_on_count:
                    GPIO.output(self.manual_led_off, True)
                    self.manual_led_state = False
                else:
                    GPIO.output(self.manual_led_off, False)
                    self.manual_led_state = True
                if self.led_counter >= self.auto_led_on_count:
                    GPIO.output(self.auto_led_off, True)
                    self.auto_led_state = False
                else:
                    GPIO.output(self.auto_led_off, False)
                    self.auto_led_state = True
                self.led_counter += 1
                time.sleep(self.cycle_duration) # cycle_duration sets the time increments for the flashing of the LED
            else:
                self.led_counter = 0

class NorthcliffDoorbellMonitor(object): # The class for the main door monitor program
    def __init__(self, pushover_in_manual_mode, full_video, ask_for_auto_time_input, active_auto_start, active_auto_finish, disable_weekend,
                 manual_mode_call_sip_address, pushover_token, pushover_user, linphone_debug_log_file, auto_message_file,
                 auto_video_capture_directory, linphone_config_file, auto_on_startup, linphone_in_manual_mode, heartbeat_enabled):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Set up the non-LED GPIO ports
        self.manual_button = 17
        self.auto_button = 22
        self.door_bell_not_ringing = 24
        self.open_door = 18
        GPIO.setup(self.door_bell_not_ringing, GPIO.IN)
        GPIO.setup(self.open_door, GPIO.OUT)
        GPIO.setup(self.manual_button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.auto_button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.add_event_detect(self.manual_button, GPIO.RISING, self.process_manual_button, bouncetime=300)
        GPIO.add_event_detect(self.auto_button, GPIO.RISING, self.process_auto_button, bouncetime=300)
        # Set up status flags
        self.idle_mode_enabled = True
        self.manual_mode_enabled = False
        self.auto_mode_enabled = False
        self.triggered = False
        self.shutdown = False
        self.ringing = False
        # Set up pushover and linphone
        self.manual_mode_call_sip_address = manual_mode_call_sip_address
        self.pushover_token = pushover_token
        self.pushover_user = pushover_user
        self.linphone_debug_log_file = linphone_debug_log_file
        self.auto_message_file = auto_message_file
        self.auto_video_capture_directory = auto_video_capture_directory
        self.linphone_config_file = linphone_config_file
        self.ask_for_auto_time_input = ask_for_auto_time_input
        self.pushover_in_manual_mode = pushover_in_manual_mode
        self.auto_on_startup = auto_on_startup
        self.linphone_in_manual_mode = linphone_in_manual_mode
        self.heartbeat_enabled = heartbeat_enabled
        if full_video == True:
            self.linphone_video_parameter = "V"
            print("Full Video Mode")
        else:
            self.linphone_video_parameter = "C" # Capture-only Video Mode
        # Set up auto start and finish times
        if self.ask_for_auto_time_input == False:
            self.active_auto_start = active_auto_start
            self.active_auto_finish = active_auto_finish
            self.disable_weekend = disable_weekend
        # Set up mqtt comms
        self.client = mqtt.Client('doorbell') # Create new instance of mqtt Class
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("<Your mqtt Broker Here>", 1883, 60) # Connect to mqtt broker
        self.client.loop_start() # Start mqtt monitor thread
        self.client.subscribe('DoorbellButton')
        self.disable_doorbell_ring_sensor = False # Enable doorbell ring sensor
        self.entry_door_open = False
        self.heartbeat_count = 0
        self.no_heartbeat_ack = False
        self.linphone_active = False

    def on_connect(self, client, userdata, flags, rc):
        time.sleep(1)
        self.print_status("Connected to mqtt server with result code "+str(rc)+" on ")
        
    def on_message(self, client, userdata, msg): #Process mqtt messages
        decoded_payload = str(msg.payload.decode('utf-8'))
        parsed_json = json.loads(decoded_payload)
        #print(parsed_json)
        if str(msg.topic) == 'DoorbellButton':
            if parsed_json['service'] == 'Automatic':
                self.process_auto_button(self.auto_button)
            elif parsed_json['service'] == 'Manual':
                self.process_manual_button(self.manual_button)
            elif parsed_json['service'] == 'OpenDoor':
                self.open_and_close_door()
            elif parsed_json['service'] == 'UpdateStatus':
                self.update_status()
            elif parsed_json['service'] == 'DoorStatusChange':
                self.process_door_status_change(parsed_json)
            elif parsed_json['service'] == 'Heartbeat Ack':
                self.heartbeat_ack()
            else:
                print('invalid button')

    def process_manual_button(self, channel):
        self.print_status("Manual Button Pressed on ")
        self.triggered =  False
        self.ringing = False
        if self.manual_mode_enabled == False:
            self.idle_mode_enabled = False
            self.manual_mode_enabled = True
            self.auto_mode_enabled = False
            self.manual_mode_startup(normal_manual_flash = True)
        else:
            self.manual_mode_enabled = False
            self.idle_mode_enabled = True
            self.idle_mode_startup()
                
    def process_auto_button(self, channel):
        self.print_status("Auto Button Pressed on ")
        self.triggered = False
        self.ringing = False
        if self.auto_mode_enabled == False:
            self.idle_mode_enabled = False
            self.auto_mode_enabled = True
            self.manual_mode_enabled = False
            self.auto_mode_attempt = True
        else:
            self.auto_mode_enabled = False
            self.idle_mode_enabled = True
            self.idle_mode_startup()

    def process_door_status_change(self, parsed_json):
        if parsed_json['door'] == 'Entry Door':
            if parsed_json['new_door_state'] == 1: # If the door is now open
                self.entry_door_open = True
                self.print_status("Entry Door Opened. Automatic Answer Not Possible on ")
            else: # If the door is now closed
                self.entry_door_open = False
                self.print_status("Entry Door Closed. Automatic Answer Now Possible if in hours on ")
            self.update_status()

    def heartbeat_ack(self):
        #self.print_status('Heartbeat received from Home Manager on ')
        self.heartbeat_count = 0
        self.no_heartbeat_ack = False

    def update_status(self): #Send status to Homebridge Manager
        self.status = json.dumps({'service': 'Status Update', 'Idle': self.idle_mode_enabled, 'Automatic': self.auto_mode_enabled, 'AutoPossible': self.auto_possible(), 'Manual': self.manual_mode_enabled, 'Triggered': self.triggered, 'Terminated': self.shutdown, 'Ringing': self.ringing})
        self.client.publish("DoorbellStatus", self.status)
        
    def print_status(self, print_message):
        today = datetime.now()
        print(print_message + today.strftime('%A %d %B %Y @ %H:%M:%S'))

    def input_auto_mode_times(self):
        self.active_auto_start = int(input("Enter the 'Auto Answer Start Hour' in 24 hour format: "))
        self.active_auto_finish = int(input("Enter the 'Auto Answer Finish Hour' in 24 hour format: "))
        weekday_only = input("Disable Auto Mode on weekends? (y/n): ")
        if weekday_only == "y":
            self.disable_weekend = True
        else:
            self.disable_weekend = False
                    
    def idle_mode_startup(self):
        self.flash_leds.manual_led_on_count = 1 # Short LED Flash
        self.flash_leds.auto_led_on_count = 1 # Short LED Flash
        self.flash_leds.led_counter = 0
        self.idle_mode_enabled = True
        if self.linphone_in_manual_mode == True and self.linphone_active == True:
            self.stop_linphone()
        self.print_status("Doorbell Monitor Idle on ")
        self.update_status()

    def auto_mode_startup(self):
        self.flash_leds.manual_led_on_count = 0 # LED Off
        if self.triggered == False:
            self.flash_leds.auto_led_on_count = 20 # LED On
        else:
            self.flash_leds.auto_led_on_count = 10 # 50% LED Flash
        self.flash_leds.led_counter = 0
        self.print_status("Doorbell Monitor Auto Answer on ")
        if self.linphone_in_manual_mode == True and self.linphone_active == True:
            self.stop_linphone()
        self.update_status()

    def manual_mode_startup(self, normal_manual_flash):
        if self.triggered == False:
            self.flash_leds.manual_led_on_count = 20 # LED On to show that Manual Mode has been set up and has not been triggered
        else:
            self.flash_leds.manual_led_on_count = 10 # 50% LED Flash if the doorbell has been triggered
        if normal_manual_flash == True: # Manual Mode has been invoked through setting manual mode (rather than because the hours are outside auto being possible)
            self.flash_leds.auto_led_on_count = 0 # LED Off
        else: # Manual Mode has been invoked in out of hours auto mode
            self.flash_leds.auto_led_on_count = 1 # Short LED Flash to indicate that it's in manual mode because the time is outside auto being possible
        self.flash_leds.led_counter = 0
        self.print_status("Doorbell Monitor Manual Answer on ")
        if self.linphone_in_manual_mode == True:
            self.start_linphone()
        self.update_status()
        
    def idle_mode(self):
        if GPIO.input(self.door_bell_not_ringing) == False and self.disable_doorbell_ring_sensor == False: #if the doorbell is rung and not disabled
            self.print_status("Someone rang the bell on ")
            self.ringing = True
            print("Updating Ring Status True")
            self.update_status()
            self.ringing = False
            time.sleep(2)
            self.capture_video()
            self.push_picture = True # Attach a picture
            self.send_pushover_message(self.pushover_token, self.pushover_user, "Doorbell is ringing while in idle mode", "magic")
            self.update_status()
        
    def auto_mode(self):
        if GPIO.input(self.door_bell_not_ringing) == False and self.disable_doorbell_ring_sensor == False: #if the doorbell is rung and not disabled
            self.flash_leds.manual_led_on_count = 0 # LED Off
            self.flash_leds.auto_led_on_count = 10 # 50% LED Flash
            self.flash_leds.led_counter = 0
            self.print_status("Someone rang the bell while in auto mode on ")
            self.triggered = True
            self.ringing = True
            self.update_status()
            self.ringing = False
            time.sleep(2)
            self.capture_video() # Capture picture before door opens
            self.play_message()
            self.push_picture = True # Tells Pushover to send a picture
            self.open_and_close_door()
            self.send_pushover_message(self.pushover_token, self.pushover_user, "Doorbell is ringing while in auto mode", "updown")
            self.capture_video() # Capture picture after door opens
            self.send_pushover_message(self.pushover_token, self.pushover_user, "Second Auto Mode picture capture", "magic")
            self.update_status()
            
    def manual_mode(self):
        if GPIO.input(self.door_bell_not_ringing) == False and self.disable_doorbell_ring_sensor == False: #if the doorbell is rung and not disabled
            self.flash_leds.manual_led_on_count = 10 # 50% LED Flash
            self.flash_leds.led_counter = 0
            self.print_status("Someone rang the bell while in manual mode on ")
            self.triggered = True
            self.ringing = True
            self.update_status()
            self.ringing = False
            time.sleep(2)
            self.capture_video()          
            if self.linphone_in_manual_mode == True:
                print("Calling Linphone")
                subprocess.call(['linphonecsh dial ' + self.manual_mode_call_sip_address], shell=True)
                time.sleep(30)
                print("Terminating Linphone call")
                subprocess.call(["linphonecsh generic 'terminate'"], shell=True) # Terminate linphone call
            if self.pushover_in_manual_mode == True:
                print("Sending Pushover Message")
                self.push_picture = True # Attach a picture
                self.send_pushover_message(self.pushover_token, self.pushover_user, "Doorbell rang while in manual mode", "bugle")
            self.update_status()

    def play_message(self):
        print("Playing message")
        subprocess.call(['aplay -D front:CARD=Device,DEV=0 ' + self.auto_message_file], shell=True)

    def send_pushover_message(self, token, user, pushed_message, alert_sound):
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        if self.push_picture == False: # No picture is to be pushed
            conn.request("POST", "/1/messages.json",
             urllib.parse.urlencode({
                            "token": token,
                            "user": user,
                            "html": "1",
                            "title": "Doorbell",
                            "message": pushed_message,
                            "sound": alert_sound,
                            }), { "Content-type": "application/x-www-form-urlencoded" })
        else: # Picture is to be pushed
            r = requests.post("https://api.pushover.net/1/messages.json", data = {
                            "token": token,
                            "user": user,
                            "title": "Doorbell",
                            "message": pushed_message,
                            "sound": alert_sound
            },
            files = {
                "attachment": ("image.jpg", open(self.picture_file_name, "rb"), "image/jpeg")
            })
            
    def open_and_close_door(self):
        self.disable_doorbell_ring_sensor = True # To avoid triggering doorbell ring sensor when door is opened and closed
        GPIO.output(self.open_door, True)
        self.print_status("Door unlocked on ")
        time.sleep(3)
        GPIO.output(self.open_door, False)
        self.print_status("Door locked on ")
        self.disable_doorbell_ring_sensor = False # Reactivate doorbell ring sensor

    def capture_video(self):
        today = datetime.now()
        time_stamp = today.strftime('%d%B%Y%H%M%S')
        self.picture_file_name = self.auto_video_capture_directory + time_stamp + "picturedump.jpg"
        print("Capturing picture in file " + self.picture_file_name)
        subprocess.call(["fswebcam " + self.picture_file_name], shell=True)
         
    def auto_possible(self):
        today = datetime.now()
        hour = int(today.strftime('%H'))
        day = today.strftime('%A')
        if day == "Saturday" or day == "Sunday":
            weekday = False
        else:
            weekday = True
        if self.disable_weekend == True and weekday == False:
            active_day = False
        else:
            active_day = True
        if hour >= self.active_auto_start and hour < self.active_auto_finish and active_day == True and self.entry_door_open == False:
            return True
        else:
            return False

    def start_linphone(self):
        print('Starting Linphone')
        self.linphone_active = True
        subprocess.call(['linphonecsh init -' + self.linphone_video_parameter + ' -d 1 -l ' + self.linphone_debug_log_file +
                         " -c " + self.linphone_config_file], shell=True)

    def stop_linphone(self):
        print('Stopping Linphone')
        self.linphone_active = False
        subprocess.call(['linphonecsh exit'], shell=True)
        
    def shutdown_cleanup(self):
        # Shutdown LED flashing thread
        self.flash_leds.flash_leds = False
        self.flash_leds.terminate()
        GPIO.cleanup()
        if self.linphone_in_manual_mode == True:
            self.stop_linphone()
        time.sleep(1)
        self.today = datetime.now()
        self.print_status("Doorbell Monitor Stopped on ")
        self.idle_mode_enabled = False
        self.manual_mode_enabled = False
        self.auto_mode_enabled = False
        self.triggered = False
        self.ringing = False
        self.shutdown = True
        self.update_status()
        self.client.loop_stop() # Stop mqtt monitoring thread
        
    def process_home_manager_heartbeat(self):
        if self.heartbeat_enabled == True:
            self.heartbeat_count +=1
            if self.heartbeat_count == 3000:
                #self.print_status('Sending Heartbeat to Home Manager on ')
                self.send_heartbeat_to_home_manager()
            if self.heartbeat_count > 4500:
                self.print_status('Home Manager Heartbeat Lost. Restarting code on ')
                self.no_heartbeat_ack = True
                self.shutdown_cleanup()
                time.sleep(10)
                self.restart_code()
            
    def send_heartbeat_to_home_manager(self):
        self.client.publish('DoorbellStatus', '{"service": "Heartbeat"}')
        
    def restart_code(self):
        self.client.publish('DoorbellStatus', '{"service": "Restart"}')
        self.shutdown_cleanup()
        os.system('sudo reboot')
                            
    def run(self):
        self.led_cycle_duration = 0.05
        self.led_cycle_count = 20
        self.flash_leds = TwoLedFlash(self.led_cycle_duration, self.led_cycle_count)
        self.flash_leds_thread = Thread(target=self.flash_leds.run)
        self.flash_leds_thread.start()
        self.print_status("Northcliff Doorbell Monitor Started on ")
        if self.linphone_in_manual_mode == True:
            self.start_linphone()
            time.sleep(5)
            print("Linphone Test Call on Startup")
            subprocess.call(['linphonecsh dial ' + self.manual_mode_call_sip_address], shell=True)
            time.sleep(25)
            print("Terminating Linphone Test Call")
            subprocess.call(["linphonecsh generic 'terminate'"], shell=True) # Terminate linphone call
            self.stop_linphone()
        else:
            self.capture_video() # Capture picture on startup
        if self.ask_for_auto_time_input == True:
            self.input_auto_mode_times()
        if self.disable_weekend == True:
            print ("Active Auto Mode Start at " + str(self.active_auto_start) + ":00 Hours, Active Auto Mode Finish at " + str(self.active_auto_finish)
                   + ":00 Hours, Auto Mode Disabled on Weekends")
        else:
            print ("Active Auto Mode Start at " + str(self.active_auto_start) + ":00 Hours, Active Auto Mode Finish at " + str(self.active_auto_finish)
                   + ":00 Hours, Auto Mode Enabled on Weekends")
        self.previous_auto_possible = True
        self.idle_mode_startup()
        self.auto_mode_attempt = False
        if self.auto_on_startup == True:
            self.process_auto_button(self.auto_button)
            self.auto_mode_startup()
        try:
            while True: # Run Doorbell Monitor in continuous loop
                self.current_auto_possible = self.auto_possible()
                if self.auto_mode_enabled == True and self.current_auto_possible == True:
                    if self.previous_auto_possible == False or self.auto_mode_attempt == True:
                        self.auto_mode_attempt = False
                        self.auto_mode_startup()
                    self.auto_mode()
                elif self.auto_mode_enabled == True and self.current_auto_possible == False:
                    if self.previous_auto_possible == True or self.auto_mode_attempt == True:
                        self.auto_mode_attempt = False
                        self.manual_mode_startup(normal_manual_flash = False) # Change LED Flashing in manual_mode_startup to indicate that auto has been disabled due to out of hours or door opening
                    self.manual_mode()
                elif self.manual_mode_enabled == True:
                    self.manual_mode()
                else:
                    self.idle_mode()
                self.previous_auto_possible = self.current_auto_possible
                self.process_home_manager_heartbeat()
                time.sleep(0.1)
	            
        except KeyboardInterrupt: # Shutdown on ctrl C
            # Shutdown main program
            self.shutdown_cleanup()
            
if __name__ == '__main__': # This is where to overall code kicks off
    monitor = NorthcliffDoorbellMonitor(pushover_in_manual_mode = True, full_video = False, ask_for_auto_time_input = False, active_auto_start = 7,
                                        active_auto_finish = 19, disable_weekend = True, manual_mode_call_sip_address = "<Your SIP Address Here>",
                                        pushover_token = "<Your Pushover Token Here>", pushover_user = "<Your Pushover User Here>",
                                        linphone_debug_log_file = "<Your linphone debug log file location here>", auto_message_file = "<Your auto message file location here>",
                                        auto_video_capture_directory = "<Your video capture directory location here>", linphone_config_file = "<Your linphone config file location here>",
                                        auto_on_startup = True, linphone_in_manual_mode = True, heartbeat_enabled = True)
    monitor.run()
        

