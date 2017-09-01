#!/usr/bin/python3
from playground.network.devices import Switch
from playground.network.devices import NetworkDeviceManager

import sys  
        
def main():
    """
    pnetworking initialize local/global
    pnetworking on
    pnetworking off
    pnetworking config
    pnetworking config add sw001 switch [managed]
    pnetworking config add class_switch switch remote 192.168.0.10 9090
    pnetworking config add eth0 vnic 1.2.3.4 [manual]
    pnetworking config remove class_switch
    pnetworking config connect eth0 sw001
    pnetworking route add 20174. eth0
    pnetworking route del 20174. eth0
    pnetworking route default eth0
    pnetworking enable eth0
    pnetworking disable eth0
    """
    
    args = sys.argv[1:]
    if not args:
        # print help
        return 1
    
    command = args.pop(0)
    if command == "initialize":
        pathType = args and args.pop(0) or "local"
        if pathType == "local":
            pathIndex = 0
        elif pathType == "global":
            pathIndex = 1
        else:
            print("Initialize takes 1 optional argument: local or global. Got {} instead.".format(pathType))
            return 1
        NetworkDeviceManager.InitializeConfigLocation(pathIndex)
        return 0
    
    # do initialize command processing first. Now load manager.
    manager = NetworkDeviceManager(alert=print)
    if command == "config":
        if not args:
            cfg = manager.getConfiguration()
            print(cfg)
        else:
            verb = args.pop(0)
            manager.configure(verb, args)
    elif command == "enable":
        manager.enableDevice(args.pop(0))
    elif command == "disable":
        manager.disableDevice(args.pop(0))
    elif command == "connect":
        manager.connectDevice(args.pop(0), args.pop(0))
    elif command == "on":
        manager.on()
    elif command == "off":
        manager.off()
    elif command == "route":
        if not args:
            routes = manager.getRoutes()
            print(routes)
        else:
            verb = args.pop(0)
            manager.route(verb, args)
    else:
        print("Unknown command '{}'.".format(command))
        
if __name__=="__main__":
    sys.exit(main())