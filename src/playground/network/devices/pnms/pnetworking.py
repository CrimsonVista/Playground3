#!/usr/bin/python3
from playground.network.devices.pnms import NetworkManager, DeviceStatusOutputProcessor, RoutesStatusOutputProcessor

import sys 

def failExit(msg, errorCode=-1):
    print("Error: {}".format(msg))
    sys.exit(errorCode)
        
def main():
    help = """
pnetworking: Playground Network Management System

This utility configures and controls the playground virtual
network. It is a wrapper utility for a number of smaller 
commands:

    pnetworking initialize local/global
    
    pnetworking on
    pnetworking off
    pnetworking add device device_type *args
    pnetworking remove deivce
    pnetworking enable device
    pnetworking disable device
    pnetworking config device verb *args
    
    pnetworking status [device]
    
Call pnetworking initialize local first to initialize a config
directory in ~/.playground. Or, for global installation, pnetworking
initialize global will initialize a directory under /var.
    """
    
    
    
    args = sys.argv[1:]
    
    if not args or "-h" in args or "--help" in args:
        sys.exit(help)
    
    command = args.pop(0)
    command = command.lower().strip()
    
    if command == "initialize":
        pathIndex = 0
        overwrite = False
        while args:
            nextArg = args.pop(0)
            if nextArg == "local":
                pathIndex = 0
            elif nextArg == "global":
                pathIndex = 1
            elif nextArg == "overwrite":
                overwrite = True
            else:
                failExit("Initialize got unknown option {}.".format(pathType))
        NetworkManager.InitializeConfigLocation(pathIndex, overwrite=overwrite)
        return 0
        
    manager = NetworkManager()
    manager.loadConfiguration()
    
    if command == "add":
        if not args: failExit("USAGE: add device_name device_type device_args")
        deviceName = args.pop(0)
        if not args: failExit("USAGE: add device_name device_type device_args")
        deviceType = args.pop(0)
        manager.addDevice(deviceName, deviceType, args)
    elif command == "remove":
        if not args: failExit("USAGE: remove device_name")
        deviceName = args.pop(0)
        manager.removeDevice(deviceName)
    elif command == "enable":
        if not args: failExit("USAGE: enable device_name")
        deviceName = args.pop(0)
        deviceManager = manager.getDevice(deviceName)
        if not deviceManager: failExit("Unknown device {}".format(deviceName))
        deviceManager.enable()
    elif command == "disable":
        if not args: failExit("USAGE: disable device_name")
        deviceName = args.pop(0)
        deviceManager = manager.getDevice(deviceName)
        if not deviceManager: failExit("Unknown device {}".format(deviceName))
        deviceManager.disable()
    elif command == "config":
        if not args: failExit("USAGE: config device_name verb args")
        deviceName = args.pop(0)
        if not args: failExit("USAGE: config device_name verb args")
        verb = args.pop(0)
        deviceManager = manager.getDevice(deviceName)
        if not deviceManager: failExit("Unknown device {}".format(deviceName))
        deviceManager.config(verb, args)
    elif command == "on":
        manager.on()
    elif command == "off":
        manager.off()
        
    elif command == "status":
        if args:
            deviceName = args.pop(0)
            statusProcessor = DeviceStatusOutputProcessor.DeviceProcessorFactory(manager, deviceName)
            print(statusProcessor.process(manager.getDevice(deviceName)))
        else:
            statusProcessor = DeviceStatusOutputProcessor()
            print(statusProcessor.process(manager))
    elif command == "routes":
        statusProcessor = RoutesStatusOutputProcessor()
        print(statusProcessor.process(manager))
    else:
        failExit("Unknown command '{}'.".format(command))
        
if __name__=="__main__":
    sys.exit(main())