from .PNMSDevice import PNMSDevice
from .NetworkAccessPoint import NetworkAccessPointDevice
from .NetworkManager import NetworkManager

class InterfaceDevice(PNMSDevice):
    CanConnectTo = [NetworkAccessPointDevice]
    CanRoute     = True
    
    CONFIG_OPTION_ADDRESS = "playground_address"
    
    CONFIG_VERB_CONNECT = "connect"
    CONFIG_VERB_DISCONNECT = "disconnect"
    CONFIG_VERB_ROUTE   = "route"
    CONFIG_VERBx_ADD    = "add"
    CONFIG_VERBx_REMOVE = "remove"
    
    CONFIG_ROUTE_DEFAULT = "default"
    
    

    def initialize(self, args):
        auto = self.CONFIG_TRUE
        
        address = args.pop(0)
        while args:
            nextArg = args.pop(0)
            if nextArg == "manual":
                auto = self.CONFIG_FALSE
            else:
                raise Exception("Unknown argument for creating VNIC config: {}".format(nextArg))
                
        self._config[self.CONFIG_OPTION_ADDRESS] = address
        self._config[self.CONFIG_OPTION_AUTO]    = auto
        self._config.save()
        
    def pnmsAlert(self, device, alert, alertArgs):
        if device == self.connectedTo() and alert == device.destroy:
            self.disable()
            self._disconnect()
        else: super().pnmsAlert(device, alert, alertArgs)
        
    def destroy(self):
        self._disconnect()
        for route in self.routes():
            routesApi.removeRoute(route)
        
    def address(self):
        return self._config[self.CONFIG_OPTION_ADDRESS]
        
    def tcpLocation(self):
        if not self.enabled(): return None, None
        ipAddress = "127.0.0.1" # Nic's are designed to always be localhost
        statusFile, pidFile, lockFile = self._getDeviceRunFiles()
        with open(statusFile) as f:
            port = int(f.readline().strip())
        return (ipAddress, port)
        
    def config(self, verb, args):
        verb = self._sanitizeVerb(verb)
        if verb == self.CONFIG_VERB_CONNECT:
            connectToDeviceName, = args
            self._connect(connectToDeviceName)
        elif verb == self.CONFIG_VERB_DISCONNECT:
            self._disconnect()
        elif verb == self.CONFIG_VERB_ROUTE:
            verbx, addressBlockToRoute = args
            self._route(verbx, addressBlockToRoute)
        else:
            raise Exception("Unknown configure verb {}.".format(verb))
            
    def connectedTo(self):
        connectionsView, connectionsApi = self._pnms.getSectionAPI(NetworkManager.CONNECTIONS_SECTION_NAME)
        return connectionsView.lookupConnection(self.name())
        
    def routes(self):
        routesView, routesApi = self._pnms.getSectionAPI(NetworkManager.ROUTES_SECTION_NAME)
        return routesApi.lookupRoutesForDevice(self.name())
            
    def _connect(self, connectToDeviceName):
        connectToDevice = self._pnms.getDevice(connectToDeviceName)
        if not connectToDevice:
            raise Exception("No such device {}".format(connectToDeviceName))
        connectionsView, connectionsApi = self._pnms.getSectionAPI(NetworkManager.CONNECTIONS_SECTION_NAME)
        connectionsApi.createConnectionTo(connectToDevice)
        self._deviceDependencies.add(connectToDevice)
        
    def _disconnect(self):
        connectToDevice = self.connectedTo()
        if not connectToDevice: return
        
        connectionsView, connectionsApi = self._pnms.getSectionAPI(NetworkManager.CONNECTIONS_SECTION_NAME)
        connectionsApi.disconnect()
        
    def _route(self, verbx, addressBlockToRoute):
        routesView, routesApi = self._pnms.getSectionAPI(NetworkManager.ROUTES_SECTION_NAME)
        
        if verbx == self.CONFIG_VERBx_ADD:
        
            if addressBlockToRoute == self.CONFIG_ROUTE_DEFAULT:
                routesApi.setDefaultRoute()
            else:
                routesApi.addRoute(addressBlockToRoute)
                
        elif verbx == self.CONFIG_VERBx_REMOVE:
            if addressBlockToRoute == self.CONFIG_ROUTE_DEFAULT:
                routesApi.unsetDefaultRoute()
            else:
                routesApi.removeRoute(addressBlockToRoute)
                
        else:
            raise Exception("Unknown secondary verb Route {}.".format(verbx))