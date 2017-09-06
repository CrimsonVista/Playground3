from .PNMSDevice import PNMSDevice

class NetworkAccessPointDevice(PNMSDevice):
    CONFIG_OPTION_TYPE    = "physical_connection_type"
    CONFIG_OPTION_ADDRESS = "tcp_address"
    CONFIG_OPTION_PORT    = "tcp_port"
    
    CONFIG_TYPE_MANAGED = "managed"
    CONFIG_TYPE_LOCAL   = "local"
    CONFIG_TYPE_REMOTE  = "remote"
    
    CONFIG_TYPE_DEFAULT = CONFIG_TYPE_MANAGED
    
    def _parseStatusFile(self, statusFile):
        with open(statusFile) as f:
            port = int(f.readline())
        return port
    
    def isManaged(self):
        return self._config[self.CONFIG_OPTION_TYPE] == self.CONFIG_TYPE_MANAGED
        
    def isRemote(self):
        return self._config[self.CONFIG_OPTION_TYPE] == self.CONFIG_TYPE_REMOTE
        
    def enabled(self):
        # Remote Net-AP's are not under control of this
        # pnms and and always identified as "enabled" regardless of their 
        # actual operational status.
        if self.isRemote(): return self.STATUS_ENABLED
        return super().enabled()
        
    def disable(self):
        if self.isRemote(): return
        return super().disable()
        
    def enable(self):
        if self.isRemote(): return
        return super().enable()
        
    def tcpLocation(self):
        
        if self.isManaged():
            if not self.enabled():
                return None, None
            ipAddress = "127.0.0.1"
            statusFile, pidFile, lockFile = self._getDeviceRunFiles()
            port = self._parseStatusFile(statusFile)
            return (ipAddress, port)
            
        elif self.isRemote():
            return self._config[self.CONFIG_OPTION_ADDRESS], int(self._config[self.CONFIG_OPTION_PORT])
        else:
            return "127.0.0.1", int(self._config[self.CONFIG_OPTION_PORT])
        
    
    def initialize(self, args):
        auto = self.CONFIG_TRUE
        connType = self.CONFIG_TYPE_DEFAULT
        
        while args:
            nextArg = args.pop(0)
            
            # Handle Auto Enable Options
            if nextArg == "manual":
                auto = self.CONFIG_FALSE
            elif nextArg == "auto-enable":
                auto = self.CONFIG_TRUE
            
            # Handle Config Type Options
            # managed
            # remote addr port
            # local port
            elif nextArg in [self.CONFIG_TYPE_MANAGED, self.CONFIG_TYPE_REMOTE, self.CONFIG_TYPE_LOCAL]:
                connType = nextArg

                if nextArg == self.CONFIG_TYPE_REMOTE:
                    connAddress = args.pop(0)
                if nextArg in [self.CONFIG_TYPE_REMOTE, self.CONFIG_TYPE_LOCAL]:
                    connPort = args.pop(0)

            else:
                raise Exception("Unknown argument for creating VNIC config: {}".format(nextArg))
                
        self._config[self.CONFIG_OPTION_AUTO]    = auto
        self._config[self.CONFIG_OPTION_TYPE]    = connType
        if not self.isManaged():
            if self.isRemote():
                self._config[self.CONFIG_OPTION_ADDRESS] = connAddress
            self._config[self.CONFIG_OPTION_PORT]    = connPort
        self._config.save()
        
    def config(self, verb, args):
        verb = self._sanitize(verb)
        
        raise Exception("Unknown configure verb {}.".format(verb))
        