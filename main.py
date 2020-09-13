#!/usr/bin/env python3

from glob import glob
from threading import Thread
from time import sleep

# Third party imports
import hug
from falcon import HTTP_400
from gpiozero import OutputDevice

# Path to probe device
PROBE_PATH = glob('/sys/bus/w1/devices/28*/temperature')[0]

# Add CORS middleware
api = hug.API(__name__)
api.http.add_middleware(hug.middleware.CORSMiddleware(api))


def is_float(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


@hug.object
class HotTub:
    def __init__(self):
        self.current_temp = 0
        self.goal_temp = 0
        self.jets_active = False
        self.heater_active = False
        self.heater = OutputDevice(17)
        self.read_temp_thread = Thread(target=self.read_temp)
        self.manage_temp_thread = Thread(target=self.manage_temp)

        self.read_temp_thread.start()
        self.manage_temp_thread.start()

    @hug.object.get('/temp')
    def get_current_temp(self):
        return {'result': f'{self.current_temp:.4g}'}

    @hug.object.post('/temp')
    def set_goal_temp(self, data, response):
        if data and is_float(data):
            self.goal_temp = float(data)
        else:
            response.status = HTTP_400
            return

    @hug.object.get('/goal-temp')
    def get_goal_temp(self):
        return {'result': self.goal_temp}

    @hug.object.get('/jets')
    def get_jets_active(self):
        return {'result': self.jets_active}

    @hug.object.post('/jets')
    def toggle_jets_active(self):
        self.jets_active = not self.jets_active
        return self.get_jets_active()

    def read_temp(self):
        # Update temperature in loop
        while True:
            def convert_to_fahrenheit(temp):
                return (temp * 9/5) + 32

            with open(PROBE_PATH) as f:
                raw_temp = f.read().rstrip()

            # Split string into float
            celsius = float('.'.join((raw_temp[:2], raw_temp[2:])))
            self.current_temp = convert_to_fahrenheit(celsius)

    def toggle_heater(self, enabled):
        self.heater_active = enabled
        if enabled:
            self.heater.on()
        else:
            self.heater.off()

    def manage_temp(self):
        while True:
            print(f'current_temp: {self.current_temp}')
            print(f'goal_temp: {self.goal_temp}')
            print(f'heater_active: {self.heater_active}')
            print()
            if self.current_temp < self.goal_temp:
                if not self.heater_active:
                    self.toggle_heater(True)
            else:
                if self.heater_active:
                    self.toggle_heater(False)
            
            sleep(1)

