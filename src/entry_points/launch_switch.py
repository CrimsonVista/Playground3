
import sys, os, socket
import argparse

import daemon
from daemon import pidlockfile as pidfile

def runSwitch(switch_type, host, port, statusfile):
    # Don't import anything playground or asyncio related until after the fork.
    from playground.network.devices import Switch, UnreliableSwitch
    from playground.network.protocols.spmp import SPMPServerProtocol, FramedProtocolAdapter
    from playground.common.logging import EnablePresetLogging, PRESET_NONE, PRESET_DEBUG, PRESET_LEVELS 
    import asyncio, logging

    EnablePresetLogging(PRESET_DEBUG)
    logging.getLogger("playground").debug("start")
    
    if switch_type == "unreliable":
        BaseSwitch = UnreliableSwitch
    else:
        BaseSwitch = Switch
    
    class SPMPSwitch(BaseSwitch):
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
                            "all-log-levels"       :(lambda    : ", ".join(PRESET_LEVELS)),
                            "get-log-level"        :(lambda    : self._presetLogging),
                            "set-log-level"        :(lambda lvl: self.setLogLevel(lvl)),
                            }
            if unreliable:
                self.SPMPApi.update( {
                            "get-error-rate"        :(lambda    : "Errors per Bytes = {}".format(self.getErrorRate())),
                            "set-error-rate"        :(lambda rate, horizon: self.setErrorRate(int(rate), int(horizon))),
                            "get-delay-rate"        :(lambda    : "Every {} packets, delay {} second".format(self.getDelayRate())),
                            "set-delay-rate"        :(lambda rate, delay: self.setDelayRate(int(rate), float(delay)))
                    })
                
        def ProtocolFactory(self):
            logging.getLogger("playground.SPMPSwitch").debug("Producing Protocol")
            originalProtocol = super().ProtocolFactory()
            spmpServerProtocol = SPMPServerProtocol(self, self.SPMPApi)
            framedProtocol = FramedProtocolAdapter(spmpServerProtocol, originalProtocol)
            return framedProtocol
    switch = SPMPSwitch()
    
    loop = asyncio.get_event_loop()
    coro = loop.create_server(switch.ProtocolFactory, host=host, port=port, family=socket.AF_INET)
    server = loop.run_until_complete(coro)
    servingPort = server.sockets[0].getsockname()[1]
    if statusfile:
        with open(statusfile,"w+") as f:
            f.write("{}".format(servingPort))
    logging.getLogger("playground.blah2").debug("start run forever on port {}".format(servingPort))
    loop.run_forever()
    server.close()

def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-dir", default=os.getcwd(), help="working directory for the switch process")
    parser.add_argument("--private", action="store_true", help="Only accept local connections.")
    parser.add_argument("--port", type=int, default=0, help="listening port for switch")
    parser.add_argument("--statusfile", help="file to record status; useful for communications")
    parser.add_argument("--pidfile", help="file to record pid; useful for communciations")
    parser.add_argument("--unreliable", action="store_true", default=False, help="Introduce errors on the wire")
    parser.add_argument("--no-daemon", action="store_true", default=False, help="do not launch switch in a daemon; remain in foreground")
    args = parser.parse_args()
    
    workingDir = os.path.expanduser(os.path.expandvars(args.working_dir))
    pidFileName = os.path.expanduser(os.path.expandvars(args.pidfile))
    statusFileName = os.path.expanduser(os.path.expandvars(args.statusfile))
    pidFileDir = os.path.dirname(pidFileName)
    host = None
    if args.private: host = "127.0.0.1"
    
    if args.no_daemon:
        runSwitch(args.unreliable, host, args.port, statusFileName)
        
    else:
        with daemon.DaemonContext(
            working_directory=workingDir,
            umask=0o002,
            pidfile=pidfile.TimeoutPIDLockFile(pidFileName),
            ) as context:
            
            runSwitch(args.unreliable, host, args.port, statusFileName)

if __name__=="__main__":
    main()
