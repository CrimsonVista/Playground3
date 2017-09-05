from .NetworkAccessPoint import NetworkAccessPointDevice
from playground.common.os import getCmdOutput

class SwitchDevice(NetworkAccessPointDevice):
    REGISTER_DEVICE_TYPE_NAME = "switch"
    LAUNCH_SCRIPT = "launch_switch"
    

    def _buildLaunchCommand(self, pidFile, statusFile, port):
        cmdArgs = [self.LAUNCH_SCRIPT, "--pidfile", pidFile, "--statusfile", statusFile, "--port", port]
        return cmdArgs
            
    def _launch(self, timeout=30):
        if not self.dependenciesEnabled():
            return
        
        portFile, pidFile, lockFile = self._getDeviceRunFiles()
        port = "0" # 0 picks a free port. If we weren't managed, this would be specified.
        
        cmdArgs = self._buildLaunchCommand(pidFile, portFile, port)
        getCmdOutput(*cmdArgs)
        
        running = self._waitUntilRunning(timeout=timeout)
        if not running:
            self._shutdown()
        else:
            self._pnms.postAlert(self.enable, True)
