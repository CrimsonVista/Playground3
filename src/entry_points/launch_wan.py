
import sys, os, socket
import argparse

import daemon
from daemon import pidlockfile as pidfile

def runWan(host, port, statusfile):
    # Don't import anything playground or asyncio related until after the fork.
    from playground.network.devices import HierarchyWAN
    from playground.network.protocols.spmp import LocalAccessSecurityPolicy, SPMPServerProtocol, FramedProtocolAdapter
    from playground.common.logging import EnablePresetLogging, PRESET_NONE, PRESET_DEBUG, PRESET_LEVELS 
    import asyncio, logging

    EnablePresetLogging(PRESET_DEBUG)
    logging.getLogger("playground").debug("WAN Starting")
    
    class SPMPWAN(HierarchyWAN):
        def __init__(self, *args, **kargs):
            super().__init__(*args, **kargs)
            self.buildSpmpApi()
            
        def printConnections(self):
            s = "WAN connections\n"
            for connection, router in self.currentConnections():
                s+="\t{}: {}\n".format(connection.transport.get_extra_info("peername"),
                                router.currentPrefix())
            return s
            
        def printRoutes(self):
            s = "WAN Routes\n"
            for prefix in self.getPrefixes():
                for dstPrefix, route in self.getRoutes(prefix):
                    s+="\t{}->{}: {}\n".format(prefix, dstPrefix, route)
            return s
            
        def setConnectionByName(self, name, prefix):
            for connection, router in self.currentConnections():
                if str(connection.transport.get_extra_info("peername")) == name:
                    self.setLocation(connection, prefix)
                    return "Changed"
            return "No such connection {}".format(name)
        
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

                            "list-connections"     :(lambda     : self.printConnections()),
                            "set-location"         :(lambda conn, prefix: self.setConnectionByName(conn, int(prefix))),
                            "get-loss-rate"        :(lambda     : "Routing loss odds {}".format(self.getRoutingLossRate())),
                            "set-loss-rate"        :(lambda rate: self.setRoutingLossRate(float(rate))),
                            
                            "add-switches"          :(lambda *prefixes: [self.registerLANSwitch(int(prefix)) for prefix in prefixes]),
                            "remove-switches"       :(lambda *prefixes: [self.unregisterLANSwitch(int(prefix)) for prefix in prefixes]),
                            "set-direct-connections":(lambda prefix, *directs: self.setDirectConnections(int(prefix), [int(dst) for dst in directs])),
                            "get-route"             :(lambda src, dst: "{}".format(self.getRoute(int(src), int(dst)))),
                            "get-routes"            :(lambda         : self.printRoutes())
                    }
                
        def ProtocolFactory(self):
            logging.getLogger("playground.SPMPWAN").debug("Producing Protocol for WAN")
            try:
                originalProtocol = super().ProtocolFactory()
                spmpServerProtocol = SPMPServerProtocol(self, self.SPMPApi, security=LocalAccessSecurityPolicy())
                framedProtocol = FramedProtocolAdapter(spmpServerProtocol, originalProtocol)
            except Exception as e:
                logging.getLogger("playground.SPMPWAN").error("Failed to launch.", e)
                raise e
            return framedProtocol
    WAN = SPMPWAN()
    
    loop = asyncio.get_event_loop()
    coro = loop.create_server(WAN.ProtocolFactory, host=host, port=port, family=socket.AF_INET)
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
    parser.add_argument("--working-dir", default=os.getcwd(), help="working directory for the WAN process")
    parser.add_argument("--private", action="store_true", help="Only accept local connections.")
    parser.add_argument("--port", type=int, default=0, help="listening port for WAN")
    parser.add_argument("--statusfile", help="file to record status; useful for communications")
    parser.add_argument("--pidfile", help="file to record pid; useful for communciations")
    parser.add_argument("--no-daemon", action="store_true", default=False, help="do not launch WAN in a daemon; remain in foreground")
    args = parser.parse_args()
    
    workingDir = os.path.expanduser(os.path.expandvars(args.working_dir))
    pidFileName = os.path.expanduser(os.path.expandvars(args.pidfile))
    statusFileName = os.path.expanduser(os.path.expandvars(args.statusfile))
    pidFileDir = os.path.dirname(pidFileName)
    host = None
    if args.private: host = "127.0.0.1"
    
    if args.no_daemon:
        runWan(host, args.port, statusFileName)
        
    else:
        with daemon.DaemonContext(
            working_directory=workingDir,
            umask=0o002,
            pidfile=pidfile.TimeoutPIDLockFile(pidFileName),
            ) as context:
            
            runWan(host, args.port, statusFileName)

if __name__=="__main__":
    main()
