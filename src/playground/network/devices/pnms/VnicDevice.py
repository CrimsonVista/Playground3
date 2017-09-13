from .InterfaceDevice import InterfaceDevice
from .NetworkManager import NetworkManager
from playground.common.os import isPidAlive, getCmdOutput

from playground.network.protocols.vsockets import VNICPromiscuousControl 

import asyncio

class VnicDevice(InterfaceDevice):
    REGISTER_DEVICE_TYPE_NAME = "vnic"
    LAUNCH_SCRIPT = "launch_vnic"
    
    QUERY_VERB_SET_PROMISCUOUS = "set-promiscuous-level"
    QUERY_VERB_GET_PROMISCUOUS = "get-promiscuous-level"

    def _buildLaunchCommand(self, pidFile, statusFile, vnicAddress, connAddress, connPort):
        cmdArgs = [self.LAUNCH_SCRIPT, "--pidfile", pidFile, "--statusfile", statusFile, vnicAddress, connAddress, connPort]

        return cmdArgs
        
    async def _awaitPromiscuousResult(self, prot, timeout=10):
        while prot.currentVnicLevel == None and timeout > 0.0:
            await asyncio.sleep(.1)
            timeout = timeout - .1
        if prot.currentVnicLevel == None:
            raise Exception("Could not get a response from VNIC as to its promiscuity level.")
        return prot.currentVnicLevel
        
    def _setGetPromiscuous(self, level):
        addr, port = self.tcpLocation()
        if not addr or not port:
            raise Exception("Cannot set or get promiscuity unless devices is running.")
        loop = asyncio.get_event_loop()
        
        coro = loop.create_connection(lambda: VNICPromiscuousControl(level), host=addr, port=port)
        if loop.is_running():
            (transport, protocol) = asyncio.wait_for(coro, timeout=10)
            result = asyncio.wait(self._awaitPromiscuousResult(protocol))
        else:
            (transport, protocol) = loop.run_until_complete(coro)
            result = loop.run_until_complete(self._awaitPromiscuousResult(protocol))
        return result
        
    def query(self, verb, args):
        verb = self._sanitizeVerb(verb)
        if verb == self.QUERY_VERB_SET_PROMISCUOUS:
            newLevel, = args
            newLevel = int(newLevel)
            return self._setGetPromiscuous(newLevel)
        elif verb == self.QUERY_VERB_GET_PROMISCUOUS:
            return self._setGetPromiscuous(None)
            
        else:
            raise Exception("Unknown query {} for VNIC device.".format(verb))
            
    def _launch(self, timeout=30):
        if not self.dependenciesEnabled():
            return
        
        # convert from string name to managed class
        connectedToDeviceName = self.connectedTo()
        connectedToDevice = self._pnms.getDevice(connectedToDeviceName)
        
        if not connectedToDevice.enabled():
            raise Exception("Cannot enable VNIC until {} is enabled.".format(connectedToDevice.name()))
        connAddress, connPort = connectedToDevice.tcpLocation()
        
        # A connAddress of None means the "public" interface. Should still
        # be able to connect via localhost
        if connAddress == None:
            connAddress = "127.0.0.1"
        
        vnicAddress = self._config["playground_address"]
        
        portFile, pidFile, lockFile = self._getDeviceRunFiles()
        
        cmdArgs = self._buildLaunchCommand(pidFile, portFile, vnicAddress, connAddress, str(connPort))
        getCmdOutput(*cmdArgs)
        
        running = self._waitUntilRunning(timeout=timeout)
        if not running:
            self._shutdown()
        else:
            self._pnms.postAlert(self.enable, True)
        