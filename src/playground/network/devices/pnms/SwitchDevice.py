from .NetworkAccessPoint import NetworkAccessPointDevice
from playground.common.os import getCmdOutput

class SwitchDevice(NetworkAccessPointDevice):
    REGISTER_DEVICE_TYPE_NAME = "switch"
    LAUNCH_SCRIPT = "launch_switch"
    

    def _buildLaunchCommand(self, pidFile, statusFile, port, *extras):
        cmdArgs = [self.LAUNCH_SCRIPT, "--pidfile", pidFile, "--statusfile", statusFile, "--port", port]
        return cmdArgs + list(extras)
            
    def _launch(self, timeout=5):
        if not self.dependenciesEnabled():
            return
        if self.isRemote():
            raise Exception("Cannot launch remote switches")
        elif self.isManaged():
            port = "0" # pick next free port
        else:
            port = self._config[self.CONFIG_OPTION_PORT]
        
        portFile, pidFile, lockFile = self._getDeviceRunFiles()

        
        cmdArgs = self._buildLaunchCommand(pidFile, portFile, port)
        
        if self.isLocal():
            cmdArgs.append("--private")
        
        output = getCmdOutput(*cmdArgs)
        
        running = self._waitUntilRunning(timeout=timeout)
        if not running:
            if output: print(output)
            self._shutdown()
        else:
            self._pnms.postAlert(self.enable, True)
