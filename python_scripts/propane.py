import os

CONFIG_FILE_DIR           = "/root/config/data"
RELAY_THRESHOLDS_FILENAME = "relay_thresholds.txt"

def read_propane_thresholds():
    global PropaneThresholds

    PropaneThresholds = {}
            
    path = CONFIG_FILE_DIR + "/" + RELAY_THRESHOLDS_FILENAME
    if os.path.exists(path):
        inputFile = open(path, 'r')
        for line in inputFile:
            (pct, thresh) = line.split(',')
            PropaneThresholds[pct] = thresh.strip()

            lastVal = 0
            for item, next_item in self.iterate(sorted(PropaneThresholds.iterkeys(), key=int)):
                if next_item is not None and \
                    PropaneThresholds[item] > PropaneThresholds[next_item]:
                    logger.warn("WARNING: propane thresholds out of order: %s(%d) < %s(%d)" \
                                     % (item, int(PropaneThresholds[item]),
                                        next_item, int(PropaneThresholds[next_item])))
                lastVal = PropaneThresholds[item]
                logger.debug("%s - next %s" % (str(item), str(next_item)))


# Main

reading = int(data.get("reading"))
read_propane_thresholds()
