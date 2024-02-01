import appdaemon.plugins.hass.hassapi as hass
from appdaemon.appdaemon import AppDaemon

import os
import time
import datetime
from collections import OrderedDict

CONFIG_FILE_DIR           = "/config/data"
RELAY_THRESHOLDS_FILENAME = "relay_thresholds.txt"

propane_thresholds = None
max_reading        = None
#simulate           = None
simulate           = 1800
#
# Read Propane Level
#
# Args:
#

class PropaneLevel(hass.Hass):
    def initialize(self):
        self.listen_event(self.handle_calibrate_propane_sensor_req, "calibrate_propane_sensor")
        self.listen_event(self.handle_update_propane_level_req, "update_propane_level")
            
        # Prevent infinite loop if signal continuously updates
        # self.listen_state(self.mimolite_sensor_update, "sensor.mimolite_general_purpose")

    def read_propane_thresholds(self):
        global propane_thresholds
        global max_reading

        propane_thresholds = OrderedDict()

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
            
        max_reading = float(propane_thresholds[sorted(propane_thresholds, key=float)[-1]])
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
            #self.call_service("var/set", entity_id='var.propane_alert', value=status)
            self.send_notification(status)

    def send_notification(self, alert):
        self.log("Alerting: %s" % alert)
        self.call_service("notify/pushover", message=alert)

    def get_propane_sensor_reading(self):

        """Return the current sensor reading, either from mimolite or
        a test value.
        """

        reading = 0
        if simulate is None:
            reading = float(self.read_mimolite())
        else:
            reading = float(simulate)

        self.log("Propane sensor reading (%d)" % reading)
        return reading

    def read_mimolite(self, entity=None, data=None, kwargs=None):
        """Use Mimolite to obtain a good sensor reading, and return
        it.  If a good reading cannot be obtained after multiple
        attempts, return None.
        """
    
#        self.log("Setting MimoLite Relay Delay")
#        self.call_service("zwave_js/set_config_parameter", node_id='19', parameter='11', value='300')
        #        self.call_service("zwave_js/set_config_parameter", device_id='f61ad85870bb394b844107e1f3a59e79', parameter=11, value=150)

        retry=0
        reading = None
        while not reading and retry < 3:
            self.log("Turning On Relay")
            self.turn_on("switch.mimolite_current_value")
            self.log("Queueing Sensor Read")
            #self.call_service("zwave_js.refresh_value", node_id=19, value_id='72057594361692194')
            self.call_service("zwave_js/refresh_value", entity_id="sensor.mimolite_general_purpose")
            reading = int(float(self.get_state("sensor.mimolite_general_purpose", "state")))
            self.log("Turning Off Relay")
            self.turn_off("switch.mimolite_current_value")

            if reading < 100 or reading > int(max_reading):
                self.log("Bad mimolite reading: %d" % reading)
                reading = None
                time.sleep(3)
                retry += 1
                
        self.call_service("var/set", entity_id='var.last_mimolite_reading', value=reading)
        updated = datetime.datetime.today().strftime('%m/%d/%Y  %H:%M:%S')
        self.call_service("var/set", entity_id='var.last_mimolite_update', value=updated)
        self.log("Mimolite current reading: %d" % reading)
        return reading

    def calculate_propane_level_percentage(self, sensor):
        """Given a sensor reading, calculate the tank level percentage
        using the thresholds list.
        """
        prev_pct    = None
        prev_thresh = None
        calc_pct    = None
        
        last_pct = list(sorted(propane_thresholds.keys()))[-1]
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

        return calc_pct

    def handle_calibrate_propane_sensor_req(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        """Handle request to calibrate the sensor reading / pct
        threholds and update the threshold list.
        """
        global propane_thresholds

        calibrate_pct = float(self.get_state("input_number.propane_gauge_pct", "state"))
        self.call_service("var/set", entity_id='var.calibration_status', value="PROCESSING")
        self.call_service("var/set", entity_id='var.calibration_result', value=f"REQ: Calibrate to {calibrate_pct}")

        self.read_propane_thresholds()
        self.log(f"Received request to calibrate sensor reading to: {calibrate_pct}%")
            
        first_reading = float(propane_thresholds[sorted(propane_thresholds, key=float)[0]])
        last_reading = float(propane_thresholds[sorted(propane_thresholds, key=float)[-1]])

        first_pct = sorted(propane_thresholds, key=float)[0]
        last_pct = sorted(propane_thresholds, key=float)[-1]
        
        self.log(f"First: {first_pct}/{first_reading} Last: {last_pct}/{last_reading}")

        self.log("CURRENT THRESHOLDS:")
        for k, v in propane_thresholds.items():
            # thresh = float(propane_thresholds[pct])
            self.log(f"\tCurrent Threshold:  {v} @ {k}")
            
        # Take reading
        reading = float(self.get_propane_sensor_reading())
        self.log(f"Current reading: {reading}")

        # Boundary Case 1a: Reading is lower than current lowest
        if reading < first_reading:
            # Remove existing entries having lower pct than given one,
            # with a higher reading
            done = False
            while not done:
                for k, v in propane_thresholds.items():
                    done = True
                    if k < calibrate_pct:
                        self.log(f"Removing out of boundary low threshold: {v} @ {k}")
                        del propane_thresholds[k]
                        done = False
                        break

        # Boundary Case 1b: Pct is lower than lowest but reading is
        # higher
        if calibrate_pct < first_pct:
            # Remove existing entries having lower reading than the new one
            done = False
            while not done:
                for k, v in propane_thresholds.items():
                    done = True
                    if float(v) < reading:
                        self.log(f"Removing out of boundary low pct threshold: {v} @ {k}")
                        del propane_thresholds[k]
                        done = False
                        break
  
        # Boundary Case 2: Reading is higher than current highest
        if reading > last_reading:
            # Remove existing entries having lower pct than given one,
            # with a higher reading
            done = False
            while not done:
                for k, v in reversed(propane_thresholds.items()):
                    done = True
                    if k > calibrate_pct:
                        self.log(f"Removing out of boundary high threshold: {v} @ {k}")
                        del propane_thresholds[k]
                        done = False
                        break

        # Boundary Case 2b: Pct is highter than highest but reading is
        # lower
        if calibrate_pct > last_pct:
            # Remove existing entries having higher reading than the new one
            done = False
            while not done:
                for k, v in reversed(propane_thresholds.items()):
                    done = True
                    if float(v) > reading:
                        self.log(f"Removing out of boundary low pct threshold: {v} @ {k}")
                        del propane_thresholds[k]
                        done = False
                        break
                    
        # Boundry Case 3: Reading invalidates existing thresholds it
        # falls between
        done = False
        while not done:
            for k, v in propane_thresholds.items():
                done = True
                if calibrate_pct < k and reading > float(v):
                    self.log(f"Removing invalid order threshold: {v} @ {k}")
                    del propane_thresholds[k]
                    done = False
                    break

                
        propane_thresholds[calibrate_pct] = reading

        resorted_thresholds = OrderedDict()
        for v in sorted(propane_thresholds.keys()):
            resorted_thresholds[v] = propane_thresholds[v]

        propane_thresholds = resorted_thresholds
        
        self.log("UPDATED THRESHOLDS:")
        for k, v in propane_thresholds.items():
            self.log(f"\tThreshold:  {v} @ {k}")
        
        self.call_service("var/set", entity_id='var.calibration_status', value="UPDATED")
        updated = datetime.datetime.today().strftime('%m/%d/%Y  %H:%M:%S')
        self.call_service("var/set", entity_id='var.calibration_result', value=f"Calibrated to {calibrate_pct} with {reading} @ {updated}")
        self.write_propane_thresholds()
        
    def handle_update_propane_level_req(self, entity=None, data=None, arg1=None, arg2=None, arg3=None):
        """Handle an incoming event request to update the current
        propane tank percent full level.  The actual tank sensor will
        be checked, unless a simulate value is specified, in which
        that will be used and the sensor check will be skipped.
        """

        self.log("Get Propane Level triggered")
        self.read_propane_thresholds()
        retry = 0

        calc_pct = None
        sensor = self.get_propane_sensor_reading()
        calc_pct = self.calculate_propane_level_percentage(sensor)

        if not calc_pct:
            self.log("Could not obtain a good reading; aborting")
            return

        calc_pct = round(calc_pct, 1)

        prev_pct_state = float(self.get_state("var.propane_percentage", "state"))
        self.call_service("var/set", entity_id='var.prev_propane_percentage', value=prev_pct_state)
        self.call_service("var/set", entity_id='var.propane_percentage', value=calc_pct)
        self.log("Propane level is %f (prev=%f)" % (calc_pct, prev_pct_state))

        if (calc_pct - prev_pct_state > 10) and calc_pct > 50 and prev_pct_state > 5.0:
            status = "Propane has been refilled to (%d%%)" % (calc_pct)
            self.send_notification(status)
            #self.call_service("var/set", entity_id='propane_alert', value=status)

        self.check_low_level(50, calc_pct, prev_pct_state)
        self.check_low_level(40, calc_pct, prev_pct_state)
        self.check_low_level(30, calc_pct, prev_pct_state)
        self.check_low_level(20, calc_pct, prev_pct_state)

