from .network.devices.vnic import connect
from .common import logging as logging_control

# enable our own handler to prevent python from creating a default one.
logging_control.EnablePresetLogging(logging_control.PRESET_NONE)

