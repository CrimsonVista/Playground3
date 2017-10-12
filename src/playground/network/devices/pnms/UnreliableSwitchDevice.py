from .NetworkAccessPoint import NetworkAccessPointDevice
from playground.common.os import getCmdOutput
from playground.network.protocols.spmp import SPMPClientProtocol, FramedProtocolAdapter
import asyncio

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
            
    def query(self, verb, args):
        addr, port = self.tcpLocation()
        loop = asyncio.get_event_loop()
        coro = loop.create_connection(lambda: FramedProtocolAdapter(SPMPClientProtocol()), host=addr, port=port)
        if loop.is_running():
            (transport, protocol) = asyncio.wait_for(coro, timeout=10)
            result, error = asyncio.wait(protocol.spmp.query(verb, *args))
        else:
            (transport, protocol) = loop.run_until_complete(coro)
            result, error = loop.run_until_complete(protocol.spmp.query(verb, *args))
        if error != None:
            raise Exception(error)
        return result
