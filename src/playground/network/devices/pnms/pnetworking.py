#!/usr/bin/python3
from playground.network.devices.pnms import NetworkManager, DeviceStatusOutputProcessor, RoutesStatusOutputProcessor
from playground import Configure

import sys, traceback

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
    pnetworking query device verb *args
    
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
    
    try:
        processCommand(command, args)
    except Exception as e:
        print("Error executing '{}':".format(command))
        print("\t{}".format(e))
        response = input("See stack trace [y/N]? ")
        if response.lower().startswith('y'):
            traceback.print_tb(e.__traceback__)
            print("\n")
        
def processCommand(command, args):
    
    if command == "initialize":
        pathId = Configure.INSTANCE_CONFIG_KEY
        overwrite = False
        while args:
            nextArg = args.pop(0)
            if nextArg.upper() in Configure.SEARCH_PATHS.keys():
                pathId = nextArg.upper()
            elif nextArg == "overwrite":
                overwrite = True
            else:
                failExit("Initialize got unknown option {}.".format(nextArg))
        Configure.Initialize(pathId, overwrite=overwrite)
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
    elif command == "query":
        if not args: failExit("USAGE: config device_name verb args")
        deviceName = args.pop(0)
        if not args: failExit("USAGE: config device_name verb args")
        verb = args.pop(0)
        deviceManager = manager.getDevice(deviceName)
        if not deviceManager: failExit("Unknown device {}".format(deviceName))
        result = deviceManager.query(verb, args)
        if result != None:
            print("\tResponse: {}".format(result))
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