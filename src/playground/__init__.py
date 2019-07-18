# Initialize Playground.
# There are some complicated dependncies here. Please pay attention

# 1.
# Define the start-up directory. If the cwd changes, we'll memorialize where
# we started
import os
STARTUP_DIR = os.getcwd()

# 2.
# Import  the Configure module. This is step 2, because it needs
# to be available to all other modules being imported.
from playground.common.Configure import Configure, PlaygroundConfigFile

# 3.
# Set up logging. May require Configure
from .common import logging as logging_control

# enable our own handler to prevent python from creating a default one.
logging_control.EnablePresetLogging(logging_control.PRESET_NONE)

# 4.
# Define all other modules that need to use the configure
# directory and configure on startup. Done after logging is
# set up

# 5.
# Configure connectors
from .network.devices.vnic import connect
reloadConnectors = connect.ConnectorService.reloadConnectors
setConnector = connect.ConnectorService.setConnector
getConnector = connect.ConnectorService.getConnector
create_server = connect.create_server
create_connection = connect.create_connection
Connector    = connect.PlaygroundConnector
Configure.CONFIG_MODULES.append(connect.ConnectorService)



