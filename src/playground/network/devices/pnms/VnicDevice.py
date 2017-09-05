from .InterfaceDevice import InterfaceDevice
from .NetworkManager import NetworkManager
from playground.common.os import isPidAlive, getCmdOutput

class VnicDevice(InterfaceDevice):
    REGISTER_DEVICE_TYPE_NAME = "vnic"
    LAUNCH_SCRIPT = "launch_vnic"

    def _buildLaunchCommand(self, pidFile, statusFile, vnicAddress, connAddress, connPort):
        cmdArgs = [self.LAUNCH_SCRIPT, "--pidfile", pidFile, "--statusfile", statusFile, vnicAddress, connAddress, connPort]

        return cmdArgs
            
    def _launch(self, timeout=30):
        if not self.dependenciesEnabled():
            return
        
        # convert from string name to managed class
        connectedToDeviceName = self.connectedTo()
        connectedToDevice = self._pnms.getDevice(connectedToDeviceName)
        
        if not connectedToDevice.enabled():
            raise Exception("Cannot enable VNIC until {} is enabled.".format(connectedToDevice.name()))
        connAddress, connPort = connectedToDevice.tcpLocation()
        
        vnicAddress = self._config["playground_address"]
        
        portFile, pidFile, lockFile = self._getDeviceRunFiles()
        
        cmdArgs = self._buildLaunchCommand(pidFile, portFile, vnicAddress, connAddress, str(connPort))
        getCmdOutput(*cmdArgs)
        
        running = self._waitUntilRunning(timeout=timeout)
        if not running:
            self._shutdown()
        else:
            self._pnms.postAlert(self.enable, True)
        