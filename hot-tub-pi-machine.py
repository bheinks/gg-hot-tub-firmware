#!/usr/bin/env python3

from signal import signal, SIGTERM
from glob import glob
from threading import Thread
from time import sleep

# Third party imports
import hug
from falcon import HTTP_400
from gpiozero import OutputDevice

# Global constants
PROBE_PATH = glob('/sys/bus/w1/devices/28*/temperature')[0]
DEFAULT_GOAL_TEMP = 90
MAXIMUM_TEMP = 104

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
        self.goal_temp = DEFAULT_GOAL_TEMP

        # Relay I/O
        self.circulation_pump_relay = OutputDevice(17)
        self.jets_pump_relay = OutputDevice(22)
        self.heater_relay = OutputDevice(27)

        # Circulation pump always on
        self.circulation_pump_relay.on()

        # Background threads
        self.read_temp_thread = Thread(target=self.read_temp)
        self.manage_temp_thread = Thread(target=self.manage_temp)
        self.read_temp_thread.start()
        self.manage_temp_thread.start()

        # Handle SIGTERM
        signal(SIGTERM, self.stop)

    @hug.object.get('/temp')
    def get_current_temp(self):
        return {'result': f'{self.current_temp:.4g}'}

    @hug.object.post('/temp')
    def set_goal_temp(self, data, response):
        if data and is_float(data):
            self.goal_temp = float(data)
        else:
            response.status = HTTP_400

    @hug.object.get('/goal-temp')
    def get_goal_temp(self):
        return {'result': self.goal_temp}

    @hug.object.get('/jets')
    def get_jets_active(self):
        return {'result': bool(self.jets_pump_relay.value)}

    @hug.object.post('/jets')
    def toggle_jets_active(self):
        self.jets_pump_relay.toggle()
        return self.get_jets_active()

    def read_temp(self):
        def convert_to_fahrenheit(temp):
            return (temp * 9/5) + 32

        # Update temperature in loop
        while self.running:
            with open(PROBE_PATH) as f:
                raw_temp = f.read().rstrip()

            if raw_temp:
                # Split string into float
                celsius = float('.'.join((raw_temp[:2], raw_temp[2:])))
                self.current_temp = convert_to_fahrenheit(celsius)

    def manage_temp(self):
        while self.running:
            if self.current_temp < self.goal_temp <= MAXIMUM_TEMP:
                if not self.heater_active:
                    self.heater_relay.on()
            else:
                if self.heater_active:
                    self.heater_relay.off()

            sleep(1)

    def stop(self):
        self.running = False
        self.read_temp_thread.join()
        self.manage_temp_thread.join()

        sys.exit(0)

