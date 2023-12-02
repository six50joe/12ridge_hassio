import appdaemon.plugins.hass.hassapi as hass

#
# Door Test App
#
# Args:
#

class DoorTest(hass.Hass):

  def initialize(self):
    self.listen_state(self.signal, "sensor.front_door_alarm_level")

  def signal(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
    self.log("SIgbnalled")
