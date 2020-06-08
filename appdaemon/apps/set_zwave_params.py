import appdaemon.plugins.hass.hassapi as hass
from appdaemon.appdaemon import AppDaemon


#
# Set ZWave Device Params
#
# Args:
#

class SetDeviceParams(hass.Hass):
    def initialize(self):
        self.listen_event(self.set_params, "set_zwave_device_params")

    def set_params(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        self.log("Setting ZWave Device Parameters")
        # Front Door
        self.call_service("zwave/set_config_parameter", node_id=20, parameter=121, value=17)
        self.log("Set Front Door to report battery + Binary Report")
        self.call_service("zwave/set_config_parameter", node_id=7, parameter=121, value=17)
        self.log("Set Garage Door to report battery + Binary Report")
