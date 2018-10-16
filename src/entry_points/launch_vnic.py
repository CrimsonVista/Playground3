
### WARNING!!! ####
# This file uses daemon, which uses fork.
# asyncio can fail spectacularly on fork.
# ensure that only the minimal imports are
# called until after fork!
#
# IN SHORT, DONT IMPORT FROM PLAYGROUND OR ASYNCIO
# until AFTER the FORK
###

import os, argparse, logging

import daemon
from daemon import pidlockfile as pidfile

            
def runVnic(vnic_address, port, statusfile, switch_address, switch_port, daemon):

    # normally, all of this would be global. We have it
    # here so it is not messing with the fork!
    from playground.network.devices import VNIC
    from playground.network.protocols.spmp import HiddenSPMPServerProtocol
    from playground.common.logging import EnablePresetLogging, PRESET_NONE, PRESET_LEVELS 
    
    import asyncio
    
    logger = logging.getLogger("playground.vnic")
    class VnicStatusListeners:
        def __init__(self):
            self.reset()
            
        def alert(self, method):
            for l in self.listeners:
                l.alert(method)
                
        def reset(self):
            self.listeners = set([])
    vnicStatusListeners = VnicStatusListeners()
                
    class StatusVnic(VNIC):
        def __init__(self, *args, **kargs):
            super().__init__(*args, **kargs)
            self.buildSpmpApi()
        
        def setLogLevel(self, lvl):
            EnablePresetLogging(lvl)
            self._presetLogging = lvl
        def buildSpmpApi(self):
            self._presetLogging = PRESET_NONE
            self.SPMPApi =  {
                            "verbs"                :(lambda    : ", ".join(list(self.SPMPApi.keys()))),
                            "get-promsicuity-level":(lambda    : str(self.promiscuousLevel())),
                            "set-promiscutiy-level":(lambda lvl: self.setPromiscuousLevel(str(lvl))),
                            "all-log-levels"       :(lambda    : ", ".join(PRESET_LEVELS)),
                            "get-log-level"        :(lambda    : self._presetLogging),
                            "set-log-level"        :(lambda lvl: self.setLogLevel(lvl))
                            }
        def connectionMade(self):
            super().connectionMade()
            vnicStatusListeners.alert(self.connectionMade)
            
        def connectionLost(self):
            super().connectionLost()
            vnicStatusListeners.alert(self.connectionLost)
            
                
        def controlConnectionFactory(self):
            originalProtocol = super().controlConnectionFactory()
            spmpServerProtocol = HiddenSPMPServerProtocol(originalProtocol, self, self.SPMPApi)
            return spmpServerProtocol

    class StatusManager:
        def __init__(self, statusfile, port, switchIp, switchPort, vnic):
            self._port = port
            self._vnic = vnic
            self._statusfile = statusfile
            self._switchIp = switchIp
            self._switchPort = str(switchPort)
            
        def alert(self, event):
            if event == self._vnic.connected:
                self.writeStatus("Connected")
            elif event == self._vnic.disconnected:
                self.writeStatus("Disconnected")
                
        def writeStatus(self, status):
            #print("{} writing status {} to {}".format(self._port, status, self._statusfile))
            with open(self._statusfile, "w+") as f:
                f.write("{}\n{}\n{}".format(self._port, ":".join([self._switchIp, self._switchPort]), status))
            
        
    class ConnectToSwitchTask:
        RECONNECT_DELAY = 30
        def __init__(self, vnic, switchIp, switchPort):
            self._vnic = vnic
            self._switchIp = switchIp
            self._switchPort = switchPort
            
        def alert(self, event):
            if event == self._vnic.disconnected:
                asyncio.get_event_loop().call_later(self.RECONNECT_DELAY, self.connect)
                
        def connect(self):
            coro = asyncio.get_event_loop().create_connection(self._vnic.switchConnectionFactory, self._switchIp, self._switchPort)
            futureConnection = asyncio.get_event_loop().create_task(coro)
            futureConnection.add_done_callback(self._connectFinished)
            
        def _connectFinished(self, futureConnection):
            if futureConnection.exception() != None:
                # Couldn't connect. Try again later.
                logger.debug("Couldn't connect. Reason: {}".format(futureConnection.exception()))
                asyncio.get_event_loop().call_later(self.RECONNECT_DELAY, self.connect)
            else:
                logger.debug("Connected to Switch")
    
    #### IMPORTANT #########
    # Because the Dameon process does a fork, you need to enable logging (which creates a file)
    # after the fork! So, enable logging within runVnic, rather than outside of it.
    # EnablePresetLogging(PRESET_QUIET)
    # EnablePresetLogging(PRESET_VERBOSE)
    asyncio.get_event_loop().set_debug(enabled=True)
    logger.info("pid {} asyncio {}, asyncio loop {}".format(os.getpid(), asyncio, asyncio.get_event_loop()))
    logger.info("""
 ====================================
 | Launch VNIC (Address: {}, Pid: {})
 ====================================
 """.format(vnic_address, os.getpid()))

    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    
    vnicStatusListeners.reset() # reset listeners
    
    vnic = StatusVnic(vnic_address)
    
    # Connection to the switch is optional. That is, the VNIC should be
    # up and "operating" even if it can't connect to the switch. So
    # start the server first.    
    coro = loop.create_server(vnic.controlConnectionFactory, host="127.0.0.1", port=port)

    server = loop.run_until_complete(coro)
    servingPort = server.sockets[0].getsockname()[1]
    
    statusManager = StatusManager(statusfile, servingPort, switch_address, switch_port, vnic)
    vnicStatusListeners.listeners.add(statusManager)
    statusManager.writeStatus("Disconnected")
    
    switchConnector = ConnectToSwitchTask(vnic, switch_address, switch_port)
    vnicStatusListeners.listeners.add(switchConnector)
    switchConnector.connect()
    
    logger.info("Run Forever")
    loop.run_forever()
    logger.info("Server Close")
    server.close()
    loop.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vnic_address", help="Playground address of the VNIC")
    parser.add_argument("switch_address", help="IP address of the Playground Switch")
    parser.add_argument("switch_port", type=int, help="TCP port of the Playground Switch")
    parser.add_argument("--working-directory", default=os.getcwd(), help="working directory for vnic process")
    parser.add_argument("--port", type=int, default=0, help="TCP port for serving VNIC connections")
    parser.add_argument("--statusfile", help="file to record status; useful for communications")
    parser.add_argument("--pidfile", help="file to record pid; useful for communciations")
    parser.add_argument("--no-daemon", action="store_true", default=False, help="do not launch VNIC in a daemon; remain in foreground")
    args = parser.parse_args()
   
    workingDir = os.path.expanduser(os.path.expandvars(args.working_directory))
    pidFileName = os.path.expanduser(os.path.expandvars(args.pidfile))
    statusFileName = os.path.expanduser(os.path.expandvars(args.statusfile))
    pidFileDir = os.path.dirname(pidFileName)
    
    if args.no_daemon:
        runVnic(args.vnic_address, args.port, statusFileName, args.switch_address, args.switch_port, False)
    
    else:
        with daemon.DaemonContext(
            working_directory=workingDir,
            umask=0o002,
            pidfile=pidfile.TimeoutPIDLockFile(pidFileName),
            ) as context:
            
            runVnic(args.vnic_address, args.port, statusFileName, args.switch_address, args.switch_port, True)

if __name__=="__main__":
    main()
