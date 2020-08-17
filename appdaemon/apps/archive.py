import os
import time
import appdaemon.plugins.hass.hassapi as hass
from appdaemon.appdaemon import AppDaemon
import shlex, subprocess
import tarfile
from datetime import datetime

CONFIG_FILE_DIR    = "/config/data"
ARCHIVE_DIR        = "/config/data/archive"
APPDAEMON_LOGS_DIR = "/config/appdaemon/logs"

#
# Archive Lopgs
#
# Args:
#

class ArchiveLogs(hass.Hass):
    def initialize(self):
        self.listen_event(self.archive_logs, "create_archive")

    def make_tarfile(self, output_filename, source_dir):
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))

    def archive_logs(self, entity, data, kwargs):
        dtstr = datetime.today().strftime('%Y-%m-%d')
        archive_path = "%s/log_archive.%s.tar.gz" % (ARCHIVE_DIR, dtstr)
        
        self.log("Creating an archive at %s" % archive_path)
        self.make_tarfile(archive_path, APPDAEMON_LOGS_DIR)
        
        
        

