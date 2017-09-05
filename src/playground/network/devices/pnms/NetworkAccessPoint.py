from .PNMSDevice import PNMSDevice

class NetworkAccessPointDevice(PNMSDevice):
    CONFIG_OPTION_MANAGED = "managed"
    CONFIG_OPTION_ADDRESS = "remote_address"
    CONFIG_OPTION_PORT    = "remote_port"
    
    def _parseStatusFile(self, statusFile):
        with open(statusFile) as f:
            port = int(f.readline())
        return port
    
    def isManaged(self):
        return self._config[self.CONFIG_OPTION_MANAGED] == self.CONFIG_TRUE
        
    def enabled(self):
        # Non-managed (e.g.) remote Net-AP's are not under control of this
        # pnms and and always identified as "enabled" regardless of their 
        # actual operational status.
        if not self.isManaged(): return self.STATUS_ENABLED
        return super().enabled()
        
    def disable(self):
        if not self.isManaged(): return
        return super().disable()
        
    def enable(self):
        if not self.isManaged(): return
        return super().enable()
        
    def tcpLocation(self):
        if not self.isManaged():
            return self._config[self.CONFIG_OPTION_REMOTE_ADDRESS], self._config[self.CONFIG_OPTION_REMOTE_PORT]
        if not self.enabled():
            return None, None
        ipAddress = "127.0.0.1"
        statusFile, pidFile, lockFile = self._getDeviceRunFiles()
        port = self._parseStatusFile(statusFile)
        return (ipAddress, port)
    
    def initialize(self, args):
        auto = self.CONFIG_TRUE
        managed = self.CONFIG_TRUE
        
        while args:
            nextArg = args.pop(0)
            if nextArg == "manual":
                auto = self.CONFIG_FALSE
            elif nextArg == "managed":
                managed = self.CONFIG_TRUE
            elif nextArg == "remote":
                managed = self.CONFIG_FALSE
                remoteAddress = args.pop(0)
                remotePort = args.pop(0)

            else:
                raise Exception("Unknown argument for creating VNIC config: {}".format(nextArg))
                
        self._config[self.CONFIG_OPTION_AUTO]    = auto
        self._config[self.CONFIG_OPTION_MANAGED] = managed
        if managed == self.CONFIG_FALSE:
            self._config[self.CONFIG_OPTION_REMOTE_ADDRESS] = remoteAddress
            self._config[self.CONFIG_OPTION_REMOTE_PORT]    = remotePort
        self._config.save()
        
    def config(self, verb, args):
        verb = self._sanitize(verb)
        
        raise Exception("Unknown configure verb {}.".format(verb))