import appdaemon.plugins.hass.hassapi as hass
from appdaemon.appdaemon import AppDaemon

import os
import time
import datetime

#
# Manually set 'home' state for a person
#
# Args:
#

class HomeTracker(hass.Hass):
    def initialize(self):
        self.listen_event(self.set_home_state, "update_home_state")

    def set_home_state(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        self.log("DATA- (new way)" + str(data))
        devname = ("override_%s" % data['person'])
        self.call_service("device_tracker/see", dev_id=devname, location_name=data['state'])

