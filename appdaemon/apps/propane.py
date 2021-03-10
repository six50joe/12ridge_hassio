import appdaemon.plugins.hass.hassapi as hass
from appdaemon.appdaemon import AppDaemon

import os
import time
import datetime

CONFIG_FILE_DIR           = "/config/data"
RELAY_THRESHOLDS_FILENAME = "relay_thresholds.txt"

propane_thresholds = None
simulate           = None
#simulate           = 1768

#
# Read Propane Level
#
# Args:
#

class PropaneLevel(hass.Hass):
    def initialize(self):
        if simulate:
            self.listen_event(self.get_propane_level, "update_propane_level")
        else:
            self.listen_event(self.read_mimolite, "update_propane_level")
        self.listen_state(self.mimolite_sensor_update, "sensor.mimolite_general")

    def get_propane_sensor_reading(self):
        reading = 0
        # test_val = 1769
        test_val = None
        if test_val is None:
            reading = float(self.read_mimolite())
        else:
            reading = float(test_val)

        self.log("Propane sensor reading (%d)" % reading)
        return reading
            
    def read_mimolite(self, entity=None, data=None, kwargs=None):
        self.log("Setting MimoLite Relay Delay")
        self.call_service("zwave/set_config_parameter", node_id=19, parameter=11, value=150)
        self.log("Turning On Relay")
        self.turn_on("switch.mimolite_switch")
        self.log("Queueing Sensor Read")
        self.call_service("zwave/refresh_node_value", node_id=19, value_id='72057594361692194')
        # reading = int(float(self.get_state("sensor.mimolite_general", "state")))
        # self.log("Reading: %d" % reading)
        # return reading

    def read_propane_thresholds(self):
        global propane_thresholds

        propane_thresholds = {}

        path = CONFIG_FILE_DIR + "/" + RELAY_THRESHOLDS_FILENAME
        self.log(path)

        inputFile = open(path, 'r')
        for line in inputFile:
            self.log(line)
            (pct, thresh) = line.split(',')
            propane_thresholds[float(pct)] = thresh.strip()

        lastVal = 0
        prev_item = None
        for item in sorted(propane_thresholds, key=float):
            if prev_item is not None:
                if propane_thresholds[prev_item] > propane_thresholds[item]:
                    self.log.warn("WARNING: propane thresholds out of order: %s(%d) < %s(%d)" \
                                 % (item, int(propane_thresholds[item]),
                                    next_item, int(propane_thresholds[next_item])))
                lastVal = propane_thresholds[prev_item]
                self.log("%s - next %s" % (str(prev_item), str(item)))
            prev_item = item
        self.log("Read propane thresholds")

    def write_propane_thresholds(self):
        path = CONFIG_FILE_DIR + "/" + RELAY_THRESHOLDS_FILENAME
        if os.path.exists(path):
            backup = path + "_" + datetime.datetime.today().strftime('%Y-%m-%d_%H:%M:%S')
            os.rename(path, backup)

        outFile = open(path, 'w')

        for key in sorted(propane_thresholds, key=float):
            outFile.write("%s,%s\n" % (key, propane_thresholds[key]))

    def check_low_level(self, threshold, calc_pct, prev_pct_state):
        if calc_pct < threshold and prev_pct_state > threshold:
            status = "Propane level ( %d%% ) fell below %d%%" % (calc_pct, threshold)
            #self.call_service("variable/set_variable", variable='propane_alert', value=status)
            self.send_notification(status)

    def send_notification(self, alert):
        self.log("Alerting: %s" % alert)
        self.call_service("notify/lakehouse_hassio_joe", message=alert)
            
    def mimolite_sensor_update(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        sensor = float(self.get_state("sensor.mimolite_general", "state"))
        self.log("Reading received from mimolite: %f" % sensor)
        updated = datetime.datetime.today().strftime('%m/%d/%Y  %H:%M:%S')
        self.call_service("variable/set_variable", variable='last_mimolite_update', value=updated)
        self.get_propane_level(None, sensor)
        
    def get_propane_level(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        self.read_propane_thresholds()
        retry = 0

        prev_pct    = None
        prev_thresh = None
        calc_pct    = None
        
        last_pct = list(sorted(propane_thresholds.keys()))[-1]
        while not calc_pct and retry < 3:
            if simulate:
                # Simulation
                sensor = float(simulate)
            else: 
                sensor = data
                if sensor > 1.0 and sensor < 100.0:
                    self.log("Low reading value %f, retrying" % sensor)
                    time.sleep(30)
                    self.read_mimolite()
                    return

            self.log("Calculating pct for threshold: %f" % sensor)
            for pct in sorted(propane_thresholds, key=float):
                thresh = float(propane_thresholds[pct])
                if not calc_pct:
                    if prev_thresh:
                       thresh = float(propane_thresholds[pct])
                       self.log("%s(%d) - next %s(%d)" % (str(prev_pct),
                                                                    prev_thresh,
                                                                    str(pct), 
                                                                    thresh))
                       if prev_thresh <= sensor:
                            if pct == last_pct:
                                # This reading is above the high
                                calc_pct = pct + 1
                            if sensor <= thresh:
                                # The reading is between two thresholds
                                range_bottom = prev_thresh
                                range_top    = thresh

                                range = (range_top - range_bottom)
                                span = pct - prev_pct
                                increment = 1
                                if range > span:
                                    increment = float(range) / float(span)
                                thresh_offset = float(sensor) - float(range_bottom)

                                calc_pct = float(prev_pct) + (thresh_offset / increment)
                                self.log("range: %d span: %d increment: %f thresh_offset: %f calc_pct: %f" \
                                                  % (range, span, increment, thresh_offset, calc_pct))
                    elif sensor < thresh:
                        # Reading is below the lowest
                        calc_pct = pct - 1
                if not calc_pct:
                    prev_pct = pct
                    prev_thresh = thresh
                else:
                    break
            # Might have been a bad reading; retry
            if not calc_pct:
                self.log("possible bad value, retrying: " + str(pct))
                time.sleep(30)
                self.read_mimolite()

        calc_pct = round(calc_pct, 1)

        prev_pct_state = float(self.get_state("variable.propane_percentage", "state"))
        self.call_service("variable/set_variable", variable='prev_propane_percentage', value=prev_pct_state)
        self.call_service("variable/set_variable", variable='propane_percentage', value=calc_pct)
        self.log("Propane level is %f (prev=%f)" % (calc_pct, prev_pct_state))

        if calc_pct - prev_pct_state > 10 and calc_pct > 50 and prev_pct_state > 5.0:
            status = "Propane has been refilled to (%d%%)" % (calc_pct)
            self.send_notification(status)
            #self.call_service("variable/set_variable", variable='propane_alert', value=status)
        
        self.check_low_level(50, calc_pct, prev_pct_state)
        self.check_low_level(40, calc_pct, prev_pct_state)
        self.check_low_level(30, calc_pct, prev_pct_state)
        self.check_low_level(20, calc_pct, prev_pct_state)
