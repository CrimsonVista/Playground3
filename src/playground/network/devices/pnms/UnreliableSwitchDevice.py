from .NetworkAccessPoint import NetworkAccessPointDevice
from playground.common.os import getCmdOutput


class UnreliableSwitchDevice(NetworkAccessPointDevice):
    REGISTER_DEVICE_TYPE_NAME = "unreliable_switch"
    LAUNCH_SCRIPT = "launch_switch"
    

    def _buildLaunchCommand(self, pidFile, statusFile, port, *extras):
        cmdArgs = [self.LAUNCH_SCRIPT, "--pidfile", pidFile, "--statusfile", statusFile, "--port", port, "--unreliable"]
        return cmdArgs + list(extras)
            
    def _launch(self, timeout=30):
        if not self.dependenciesEnabled():
            return
        if self.isRemote():
            raise Exception("Cannot launch remote unreliable switches")
        elif self.isManaged():
            port = "0" # pick next free port
        else:
            port = self._config[self.CONFIG_OPTION_PORT]
        
        portFile, pidFile, lockFile = self._getDeviceRunFiles()

        
        cmdArgs = self._buildLaunchCommand(pidFile, portFile, port)
        
        if self.isLocal():
            cmdArgs.append("--private")
        
        getCmdOutput(*cmdArgs)
        
        running = self._waitUntilRunning(timeout=timeout)
        if not running:
            self._shutdown()
        else:
            self._pnms.postAlert(self.enable, True)
            
    
