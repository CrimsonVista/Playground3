
from playground.network.common import PlaygroundAddressBlock
from playground.common.datastructures import DelegateAdapter

import configparser, os, sys, time, signal

"""
Every device can only write to their section.

Devices can access global sections (e.g., routes) through
the PNMS's interface. A device only has access to the sections
granted it by the PNMS. Section access is mediated. Eg., routes
are a "lookup" table that a devicec add or remove itself from.

Playground Network Management Services:
* enabled()
* getDevice(deviceName) -> Devices get each other in r/o mode.
* getSection(sectionName)

Accessible Sections:
* Devices - Lookup device type
* Connections - Lookup connections, add self connections
* Routes - Lookup routes, add self routes
"""


class ConfigSectionAdapter(DelegateAdapter):
    ADAPTED_ATTRIBUTES = ["__setitem__", "_save", "save", "isReadOnly", "rawSection"]
    
    def __init__(self, sectionDelegate, save):
        super().__init__(sectionDelegate)
        self._save = save
    
    # Implement the following methods directly because python may bypass them.    
    def __getitem__(self, key):
        return self._delegate.__getitem__(key)
        
    def __iter__(self):
        return self._delegate.__iter__()
        
    def __delitem__(self, key):
        return self._delegate.__delitem__(key)
    ### END SPECIAL METHODS ###
        
    def __setitem__(self, key, value):
        if not self._save:
            raise Exception("Section is in read-only mode")
        self._delegate.__setitem__(key, value)
        
    def save(self):
        if not self._save:
            raise Exception("Section is in read-only mode")
        self._save()
        
    def isReadOnly(self):
        return self._save == None
        
    def rawSection(self):
        return self._delegate
    
class ConfigSectionView:
    def __init__(self, configSection):
        self._config = configSection
        self._readOnlyConfig = ConfigSectionAdapter(self._config.rawSection(), None)
        
    def rawView(self):
        return self._readOnlyConfig
 
class DevicesView(ConfigSectionView):
    def __init__(self, configSection):
        super().__init__(configSection)
    
    def lookupDeviceType(self, deviceName):
        return self._config.get(deviceName, None)
        
    def devices(self):
        return [device for device in self._config]
        
class ConnectionView(ConfigSectionView):
    def __init__(self, configSection):
        super().__init__(configSection)
        
    def lookupConnection(self, deviceName):
        return self._config.get(deviceName, None)
        
class ConnectionDeviceAPI(ConnectionView):
    # devices need to register their own conneciton rules
    PERMITTED_CONNECTION_TYPES = []
    
    @classmethod
    def ConnectionPermitted(cls, device1, device2):
        for deviceType1, deviceType2 in cls.PERMITTED_CONNECTION_TYPES:
            if isinstance(device1, deviceType1) and isinstance(device2, deviceType2):
                return True
        return False
    
    def __init__(self, configSection, connectingDevice):
        super().__init__(configSection)
        self._device = connectingDevice
        
    def createConnectionTo(self, device2):
        if not self.ConnectionPermitted(self._device, device2):
            raise Exception("No rule allowing connection of {} to {}.".format(self._device, device2))
        self._config[self._device.name()] = device2.name()
        self._config.save()
        
    def disconnect(self):
        if self._device.name() in self._config:
            del self._config[self._device.name()]
        self._config.save()
            
class RoutesView(ConfigSectionView):
    DEFAULT_ROUTE_KEY = "__default__"
    
    def __init__(self, configSection):
        super().__init__(configSection)
    
    def lookupDeviceForRoute(self, route):
        return self._config.get(route, None)
    
    def lookupRoutesForDevice(self, device):
        routes = []
        for route in self._config:
            if self._config[route] == device:
                routes.append(route)
        return routes
        
    def getDefaultRoute(self):
        return self._config.get(self.DEFAULT_ROUTE_KEY, None)
        
    def getRoutingDevice(self, address):
        for route in self._config:
            if route == self.DEFAULT_ROUTE_KEY:
                continue
            routeAddressBlock = PlaygroundAddressBlock.FromString(route)
            if routeAddressBlock.isParentBlock(address):
                return self._config[route]
        return self._config.get(self.DEFAULT_ROUTE_KEY, None)
        
class RoutesDeviceAPI(RoutesView):    
    # devices need to register their type as one that can accept routes
    PERMITTED_ROUTING_TYPES = []
    
    @classmethod
    def PermitsRouting(cls, deviceType):
        return deviceType in cls.PERMITTED_ROUTING_TYPES

    def __init__(self, configSection, routingDevice):
        super().__init__(configSection)
        self._device = routingDevice
        
        for deviceType in self.PERMITTED_ROUTING_TYPES:
            if isinstance(routingDevice, deviceType):
                allowed = True
        if not allowed:
            raise Exception("No rule allowing {} to handle routing.".format(self._device))
    
    def addRoute(self, route):
        if route in self._config:
            raise Exception("Route {} is already mapped to device {}.".format(route, self._config[route]))
        self._config[route] = self._device.name()
        self._config.save()
        
    def removeRoute(self, route):
        if not route in self._config or self._config[route] != self._device.name():
            raise Exception("{} does not have route {}.".format(self._device.name(), route))
        del self._config[route]
        
    def setDefaultRoute(self):
        self._config[self.DEFAULT_ROUTE_KEY] = self._device.name()
        self._config.save()
        
    def unsetDefaultRoute(self):
        if not self._config.get(self.DEFAULT_ROUTE_KEY, None) == self._device.name():
            raise Exception("{} does not have the default route.".format(self._device.name()))
        del self._config[self.DEFAULT_ROUTE_KEY]
        self._config.save()
    
class NetworkManager:
    SEARCH_PATHS = ["~/.playground/", "/var/playground"]
    CONFIG_FILE  = "networking.ini"
    
    DEVICES_SECTION_NAME = "devices"
    CONNECTIONS_SECTION_NAME = "connections"
    ROUTES_SECTION_NAME = "routes"
    
    SECTION_API = {
        DEVICES_SECTION_NAME:     (DevicesView, None),
        CONNECTIONS_SECTION_NAME: (ConnectionView, ConnectionDeviceAPI),
        ROUTES_SECTION_NAME:      (RoutesView, RoutesDeviceAPI)
    }
    
    REGISTERED_DEVICE_TYPES = {}
    
    @classmethod
    def InitializeConfigLocation(cls, pathIndex, overwrite=False):
        """
        This function can be used to initialize a playground network
        management config file (empty).
        """
        location = cls.SEARCH_PATHS[pathIndex]
        location = os.path.expanduser(location)
        if not os.path.exists(location):
            os.mkdir(location)
        
        configFile = os.path.join(location, cls.CONFIG_FILE) 
        if os.path.exists(configFile) and overwrite:
            os.unlink(configFile)
        if not os.path.exists(configFile):
            with open(configFile, "w+") as f:
                f.write("# Config File for Playground Networking\n") 
                
    class ReadOnlyView:
        def __init__(self, pnms, device):
            self._pnms = pnms
            self._device = device
        def enabled(self): return self._pnms.enabled()
        def location(self): return self._pnms.location()
        def getDevice(self, deviceName): return self._pnms.getDevice(deviceName, readOnly=True)
        def getSectionAPI(self, sectionName): return self._pnms.getSectionAPI(sectionName, self._device)
        def postAlert(self, alertType, args): return self._pnms.postAlert(self._device, alertType, args)

    def __init__(self):
        self._devices = {}
        self._enabled = False
        self._lastModifiedTime = None
        self._configFilePath = None
        self._configLocation = None
        
    def loadConfiguration(self, configLocation=None, configFilePath=None):
        self._configFilePath = configFilePath
        self._configLocation = configLocation
        self._loadConfig(forced=True)
        self._loadDevices()
    
    def saveConfiguration(self):
        with open(self._configFilePath, "w+") as configWriter:
            self._config.write(configWriter)
        
    def reloadConfiguration(self, forced=False):
        self._loadConfig(forced=forced)
        self._loadDevices()
        
    def location(self):
        return self._configLocation
        
    def postAlert(self, device, alertType, args):
        for deviceName in self._devices:
            self._devices[deviceName].pnmsAlert(device, alertType, args)
        
    def enabled(self):
        return self._enabled
        
    def on(self):
        """
        Currently, we don't store any state about being enabled or not.
        So this is just a macro for turning on all auto enabled devices
        """
        for deviceName in self._devices:
            if self._devices[deviceName].isAutoEnabled() and not self._devices[deviceName].enabled():
                self._devices[deviceName].enable()
    
    def off(self):
        for deviceName in self._devices:
            if self._devices[deviceName].enabled():
                self._devices[deviceName].disable()
        
    def getDevice(self, deviceName, readOnly=False):
        if deviceName in self._devices:
            return self._devices[deviceName]
        deviceType = self._config[self.DEVICES_SECTION_NAME][deviceName]
        if deviceType not in self.REGISTERED_DEVICE_TYPES:
            # TODO: Do we really want this to be an exception?
            raise Exception("Unknown device type in configuration: {}".format(deviceType))
        
        deviceClass = self.REGISTERED_DEVICE_TYPES[deviceType]
        
        deviceConfigSectionName = self._getDeviceConfigSectionName(deviceName)
        deviceConfigSection = self._getRawSectionAdapter(deviceConfigSectionName, readOnly)
        
        # return the device representation
        self._devices[deviceName] = deviceClass(deviceName)
        self._devices[deviceName].installToNetwork(self.ReadOnlyView(self, self._devices[deviceName]), deviceConfigSection)
        return self._devices[deviceName]
        
    def addDevice(self, deviceName, deviceType, deviceArgs):
        if deviceName in self._config[self.DEVICES_SECTION_NAME]:
            raise Exception("A device named {} already exists.".format(deviceName))
        if deviceType not in self.REGISTERED_DEVICE_TYPES:
            # TODO: Do we really want this to be an exception?
            raise Exception("Unknown device type in configuration: {}".format(deviceType))
            
        self._config[self.DEVICES_SECTION_NAME][deviceName] = deviceType
        
        deviceConfigSectionName = self._getDeviceConfigSectionName(deviceName)
        self._config[deviceConfigSectionName] = {}
        
        deviceManager = self.getDevice(deviceName)
        deviceManager.initialize(deviceArgs)
        self.saveConfiguration()
        
    def removeDevice(self, deviceName):
        if deviceName not in self._config[self.DEVICES_SECTION_NAME]:
            return
        deviceManager = self.getDevice(deviceName)
        
        self.postAlert(deviceManager, deviceManager.destroy, None)
        
        deviceManager.destroy()
        deviceConfigSectionName = self._getDeviceConfigSectionName(deviceName)
        
        del self._config[self.DEVICES_SECTION_NAME][deviceName]
        if deviceConfigSectionName in self._config:
            del self._config[deviceConfigSectionName]
        if deviceName in self._devices:
            del self._devices[deviceName]
            
        self.saveConfiguration()
        
        
    def _getRawSectionAdapter(self, sectionName, readOnly=False):
        if sectionName not in self._config:
            raise Exception("No such section {}".format(sectionName))
            
        if readOnly:
            save = None
        else:
            save = self.saveConfiguration
        sectionInstance = ConfigSectionAdapter(self._config[sectionName], save)
        return sectionInstance
        
    def getSectionAPI(self, sectionName, device=None):
        sectionInstance = self._getRawSectionAdapter(sectionName)
        
        view, api = None, None
        
        viewType, apiType = self.SECTION_API.get(sectionName, (None, None))
        if viewType:
            view = viewType(sectionInstance)
        if apiType and device:
            api = apiType(sectionInstance, device)
        return (view, api)
        
    def connections(self):
        connectionsView,_ = self.getSectionAPI(self.CONNECTIONS_SECTION_NAME)
        return connectionsView
        
    def routing(self):
        routingView,_ = self.getSectionAPI(self.ROUTES_SECTION_NAME)
        return routingView
        
    def deviceInfo(self):
        devicesView,_ = self.getSectionAPI(self.DEVICES_SECTION_NAME)
        return devicesView
        
    def _findConfig(self):
        for path in self.SEARCH_PATHS:
            path = os.path.expanduser(path)
            filepath = os.path.join(path, self.CONFIG_FILE)
            if os.path.exists(filepath):
                return path, filepath
        return None, None
        
    def _loadConfig(self, forced=False):
        if self._configFilePath != None:
            # we already have it set.
            if not os.path.exists(self._configFilePath):
                raise Exception("Cannot find specified config file {}".format(self._configFilePath))
            self._configLocation = os.path.dirname(self._configFilePath)
        elif self._configLocation != None:
            # have an  explicit location:
            filepath = os.path.join(self._configLocation, self.CONFIG_FILE)
            if not os.path.exists(filepath):
                raise Exception("Cannot find {} in specified config location {}".format(self.CONFIG_FILE, self._configLocation))
            self._configFilePath = filepath
        else:
            self._configLocation, self._configFilePath = self._findConfig()
            
        if not self._configFilePath:
            raise Exception("{} not found in any of {}".format(self.CONFIG_FILE, ",".join(self.SEARCH_PATHS)))
            
        newLastModifiedTime = os.path.getmtime(self._configFilePath)
        if forced or newLastModifiedTime != self._lastModifiedTime:
            self._lastModifiedTime = newLastModifiedTime
            
            self._config = configparser.ConfigParser()
            self._config.read(self._configFilePath)
            for sec in self.SECTION_API:
                if not sec in self._config:
                    self._config[sec] = {}
                            
    def _getDeviceConfigSectionName(self, deviceName):
        return "Config_{}".format(deviceName)
            
    def _loadDevices(self):
        self._devices = {}
        for deviceName in self._config[self.DEVICES_SECTION_NAME]:
            # getDevice saves it to self._devices
            self.getDevice(deviceName, readOnly=False)
