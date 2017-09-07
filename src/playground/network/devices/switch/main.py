from playground.network.devices import Switch
import asyncio, sys, os, socket
import argparse

import daemon
from daemon import pidlockfile as pidfile

def runSwitch(host, port, statusfile):
    switch = Switch()
    loop = asyncio.get_event_loop()
    coro = loop.create_server(switch.ProtocolFactory, host=host, port=port, family=socket.AF_INET)
    server = loop.run_until_complete(coro)
    servingPort = server.sockets[0].getsockname()[1]
    if statusfile:
        with open(statusfile,"w+") as f:
            f.write("{}".format(servingPort))
    loop.run_forever()
    server.close()

def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", action="store_true", help="Only accept local connections.")
    parser.add_argument("--port", type=int, default=0, help="listening port for switch")
    parser.add_argument("--statusfile", help="file to record status; useful for communications")
    parser.add_argument("--pidfile", help="file to record pid; useful for communciations")
    args = parser.parse_args()
    
    pidFileName = os.path.expanduser(os.path.expandvars(args.pidfile))
    statusFileName = os.path.expanduser(os.path.expandvars(args.statusfile))
    pidFileDir = os.path.dirname(pidFileName)
    host = None
    if args.private: host = "127.0.0.1"
    
    with daemon.DaemonContext(
        working_directory=pidFileDir,
        umask=0o002,
        pidfile=pidfile.TimeoutPIDLockFile(pidFileName),
        ) as context:
        
        runSwitch(host, args.port, statusFileName)

if __name__=="__main__":
    main()