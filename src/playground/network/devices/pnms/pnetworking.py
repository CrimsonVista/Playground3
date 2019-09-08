#!/usr/bin/python3
from playground.network.devices.pnms import NetworkManager, DeviceStatusOutputProcessor, RoutesStatusOutputProcessor
from playground import Configure

import sys, traceback, argparse, io

class SimplifiedUsageFormatter(argparse.HelpFormatter):
    """
    For our sub commands, we want to be able to get the
    subcommand and argument list without the word 'usage: '
    I can't find an easy way to do this. So we overwrite
    the formatter to use an empty prefix
    """
    def add_usage(self, usage, actions, group, prefix=None):
        return super().add_usage(usage, actions, group, prefix="")

class PnetworkingInterface:
    def initialize_subcommand_help(self):
        subcmd_help = {}
        subcmd_help["initialize"]=(
"""
\t{usage}

Command 'initialize' creates a playground infrastructure
that includes a config file and various necessary subdirectories
underneath a .playground directory. This .playground dir can be
placed in a system location for all users (with appropriate
permissions), a user location for the current user, or an instance
location, in a directory specified by PLAYGROUND_INSTANCE. The optional overwrite
argument, when set to true, will re-initialize the location erasing
the existing configuration.""").format(
            usage=self.subcommand_usage('initialize')
        )
        
        subcmd_help["on"] = (
"""
\t%{usage}

Command 'on' turns on all virtual devices for this playground location"""
        ).format(
            usage=self.subcommand_usage('on')
        )
        
        subcmd_help["off"] = (
"""
\t%{usage}

Command 'off' turns off all virtual devices for this playground location"""
        ).format(
            usage=self.subcommand_usage('off')
        )
        
        subcmd_help["add"] = (
"""
\t{usage}

Command 'add' creates a new virtual device within this playground
configuration location. The 'device' argument is just a name to call
the device. The 'device-type' argument is what kind of device, then
followed by device-type specific arguments. Currently supported
devices-types are:

{add_devices}
    """)
        add_devices = ""
        for device_type in NetworkManager.REGISTERED_DEVICE_TYPES:
            helplines = NetworkManager.REGISTERED_DEVICE_TYPES[device_type].initialize_help()
            if not helplines: continue
            # helplines may be multiple lines. tab the beginning, and every newline
            helplines = "\t"+helplines
            helplines = helplines.replace("\n","\n\t")
            add_devices += helplines +"\n"
        subcmd_help["add"] = subcmd_help["add"].format(
            usage=self.subcommand_usage('add'),
            add_devices=add_devices
        )
        
        subcmd_help["remove"] = ("""
\t%{usage}

Command 'remove' eliminates a virtual devices from this playground location"""
        ).format(
            usage=self.subcommand_usage('remove')
        )
        
        subcmd_help["config"] = (
"""
\t{usage}

Command 'config' further configures an initialized
device if necessary. Not all devices require 
configuration. Those that do include:

{add_devices}
    """)
        add_devices = ""
        for device_type in NetworkManager.REGISTERED_DEVICE_TYPES:
            helplines = NetworkManager.REGISTERED_DEVICE_TYPES[device_type].config_help()
            if not helplines: continue
            # helplines may be multiple lines. tab the beginning, and every newline
            helplines = "\t"+helplines
            helplines = helplines.replace("\n","\n\t")
            add_devices += helplines +"\n"
        subcmd_help["config"] = subcmd_help["config"].format(
            usage=self.subcommand_usage('config'),
            add_devices=add_devices
        )
        
        subcmd_help["query"] = ("""
\t{usage}

Command 'query' sends a real-time message 
to the device to ask about its state or set
state dynamically. To determine if a device
supports querying, use the following command:

    query <device> verbs
    
If the device supports querying, it will send
back a list of verbs that it understands. Otherwise,
there will be no answer.""").format(
            usage=self.subcommand_usage('query')
        )
        
        return subcmd_help

    def __init__(self, stdoutFunction=print, stderrFunction=print, failFunction=sys.exit):
        self._write = stdoutFunction
        self._error = stderrFunction
        self._fail = failFunction
        self._currentPath = None
        self._manager = None
        self.init_argument_handler()
        self._subcmd_help = self.initialize_subcommand_help()
        
    def _loadNetworkManager(self):
        try:
            self._manager = NetworkManager()
            self._manager.loadConfiguration()
        except Exception as e:
            self._fail("Could not load the network manager. {}".format(e))
            return
        
    def fail(self, msg, errorCode=-1):
        self._error("Error: {}".format(msg))
        self._fail(errorCode)
    
    def initialize_device(self, deviceName):
        device = self._manager.getDevice(deviceName)
        if not device: 
            self._fail("Unknown device {}".format(deviceName))
        return device
        
    def enable_device(self, deviceName):
        device = self.initialize_device(deviceName)
        device.enable()
        if device.enabled() == device.STATUS_ENABLED:
            self._write("{} enabled.".format(deviceName))
        elif device.enabled() == device.STATUS_ABNORMAL_SHUTDOWN:
            self._error("{} failed abnormally.".format(deviceName))
        elif device.enabled() == device.STATUS_WAITING_FOR_DEPENDENCIES:
            self._error("{} could not launch because of unmet dependencies.".format(deviceName))
        else:
            self._error("{} could not launch.".format(deviceName))
    
    def status_handler(self, args):
        if not self._currentPath:
            self._write("\nPNetworking not yet configured. Must initialize first.")
            return
            
        self._write("\nConfiguration: {}".format(self._currentPath))
        if args.device:
            statusProcessor = DeviceStatusOutputProcessor.DeviceProcessorFactory(self._manager, deviceName)
            self._write(statusProcessor.process(self._manager.getDevice(device)))
        else:
            statusProcessor = DeviceStatusOutputProcessor()
            self._write(statusProcessor.process(self._manager))
    
    def subcommand_usage(self, cmd):
        return self._commands.choices[cmd].format_usage().strip()
    
    def help_handler(self, args):
        self._write("pnetworking: Playground Network Management System")
        if self._currentPath:
            self._write("(Configuration: {})".format(self._currentPath))
        else:
            self._write("**INITIALIZATION REQUIRED**")
            
        if args.subcommand:
            help = self._subcmd_help.get(args.subcommand, "There is no help for command {}".format(args.subcommand))
            self._write("\n{}".format(help))
        else:
            self._write(
"""
This utility configures and controls the playground virtual
network. It is a wrapper utility for a number of smaller 
commands:
""")
            for subcommand in self._commands.choices:
                subcommand_usage = self.subcommand_usage(subcommand)
                self._write("\t{}".format(subcommand_usage))
                
        self._write()
        
    def init_argument_handler(self):
        self._topargs = argparse.ArgumentParser(add_help=False)
        self._preinit_functions = []
        self._topargs.set_defaults(
            func=self.help_handler
        )
        self._preinit_functions.append(self.help_handler)
        
        commands = self._topargs.add_subparsers(dest="subcommand")
        self._commands = commands
        sub_formatter = SimplifiedUsageFormatter
        
        help_parser = commands.add_parser("help", add_help=False, formatter_class=sub_formatter)
        help_parser.add_argument("subcommand",nargs="?")
        help_parser.set_defaults(
            func=self.help_handler
        )
        
        initialize_parser = commands.add_parser("initialize", add_help=False, formatter_class=sub_formatter)
        initialize_parser.add_argument("location",choices=['instance','user','system'])
        initialize_parser.add_argument("overwrite",nargs="?",default=False)
        initialize_function = lambda args: Configure.Initialize(args.location.upper(), overwrite=args.overwrite)
        initialize_parser.set_defaults(
            func = initialize_function
        )
        self._preinit_functions.append(initialize_function)
        
        on_parser = commands.add_parser("on", add_help=False, formatter_class=sub_formatter)
        on_parser.set_defaults(
            func=lambda args: self._manager.on()
        )
        
        off_parser = commands.add_parser("off", add_help=False, formatter_class=sub_formatter)
        off_parser.set_defaults(
            func=lambda args: self._manager.off()
        )
        
        add_parser = commands.add_parser("add", add_help=False, formatter_class=sub_formatter)
        add_parser.add_argument("device",type=str)
        add_parser.add_argument("device_type",type=str)
        add_parser.add_argument("args",nargs=argparse.REMAINDER)
        add_parser.set_defaults(
            func=lambda args: self._manager.addDevice(args.device, args.device_type, args.args)
        )
        
        remove_parser = commands.add_parser('remove', add_help=False, formatter_class=sub_formatter)
        remove_parser.add_argument("device",type=str)
        remove_parser.set_defaults(
            func=lambda args: self._manager.removeDevice(args.device)
        )
        
        enable_parser = commands.add_parser('enable', add_help=False, formatter_class=sub_formatter)
        enable_parser.add_argument("device",type=str)
        enable_parser.set_defaults(
            func=lambda args: self.enable_device(args.device)
        )
        
        disable_parser = commands.add_parser('disable', add_help=False, formatter_class=sub_formatter)
        disable_parser.add_argument("device",type=str)
        disable_parser.set_defaults(
            func=lambda args: self.initialize_device(args.device).disable()
        )
        
        config_parser = commands.add_parser('config', add_help=False, formatter_class=sub_formatter)
        config_parser.add_argument('device',type=str)
        config_parser.add_argument('verb',type=str)
        config_parser.add_argument('args',nargs=argparse.REMAINDER)
        config_parser.set_defaults(
            func=lambda args: self.initialize_device(args.device).config(args.verb, args.args)
        )
        
        query_parser = commands.add_parser('query', add_help=False, formatter_class=sub_formatter)
        query_parser.add_argument('device',type=str)
        query_parser.add_argument('verb',type=str)
        query_parser.add_argument('args',nargs=argparse.REMAINDER)
        query_parser.set_defaults(
            func=lambda args: self._write("\t{} Response: {}".format(
                args.device,
                self.initialize_device(args.device).query(args.verb, args.args)
            ))
        )
        
        routes_parser = commands.add_parser('routes', add_help=False, formatter_class=sub_formatter)
        routes_parser.set_defaults(
            func=lambda args: self._write(RoutesStatusOutputProcessor().process)(initialize_manager())
        )
        
        status_parser = commands.add_parser('status', add_help=False, formatter_class=sub_formatter)
        status_parser.add_argument('device',nargs='?', default=None)
        status_parser.set_defaults(func=self.status_handler)
        self._preinit_functions.append(self.status_handler)
        
        
        
    def execute(self, args):
        self._currentPath = Configure.CurrentPath()
            
        args = self._topargs.parse_args(args)
        if not self._currentPath and args.func not in self._preinit_functions:
            return self._fail("Pnetworking cannot find playground path. Try 'pnetworking help'")
        if self._currentPath:
            self._loadNetworkManager()
            
        try:
            args.func(args)
        except Exception as e:
            self._error("Error executing pnetworking")
            self._error("\t{}".format(e))
            response = input("See stack trace [y/N]? ")
            if response.lower().startswith('y'):
                writer = io.StringIO()
                traceback.print_tb(e.__traceback__, file=writer)
                self._error(writer.getvalue()+"\n")
            self._fail()
        
def main():
    interface = PnetworkingInterface()
    interface.execute(sys.argv[1:])
    sys.exit(0)
        
if __name__=="__main__":
    main()