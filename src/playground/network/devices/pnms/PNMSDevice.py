from playground.common.os import isPidAlive
from playground.common import CustomConstant as Constant
from .NetworkManager import NetworkManager, ConnectionDeviceAPI, RoutesDeviceAPI

import os, signal, time

class PNMSDeviceLoader(type):
    """
    This metaclass for PNMS device types auto loads concrete device types
    into the system.
    """
    
    @classmethod
    def loadPnmsDefinitions(cls, newClass):
        if newClass.REGISTER_DEVICE_TYPE_NAME:
            if newClass.REGISTER_DEVICE_TYPE_NAME in NetworkManager.REGISTERED_DEVICE_TYPES:
                raise Exception("Duplicate Device Type Registration")
            NetworkManager.REGISTERED_DEVICE_TYPES[newClass.REGISTER_DEVICE_TYPE_NAME] = newClass
        for deviceType in newClass.CanConnectTo:
            if not issubclass(deviceType, PNMSDevice):
                raise Exception("Connect rules requires a subclass of device type. Got {}".format(deviceType))
            rule = (newClass, deviceType)
            if not ConnectionDeviceAPI.ConnectionPermitted(newClass, deviceType):
                ConnectionDeviceAPI.PERMITTED_CONNECTION_TYPES.append(rule)
        if newClass.CanRoute:
            if not RoutesDeviceAPI.PermitsRouting(newClass):
                RoutesDeviceAPI.PERMITTED_ROUTING_TYPES.append(newClass)
    
    def __new__(cls, name, parents, dict): 
        definitionCls = super().__new__(cls, name, parents, dict)
        cls.loadPnmsDefinitions(definitionCls)
        
        return definitionCls


class PNMSDevice(metaclass=PNMSDeviceLoader):
    CONFIG_TRUE = "true"
    CONFIG_FALSE = "false"
    
    CONFIG_OPTION_AUTO = "auto_enable"
    
    """
    Sub classes that need access to the Connection section or
    Routing section need to override these values
    """
    CanConnectTo = []
    CanRoute     = False
    
    STATUS_DISABLED                 = Constant(strValue="Disabled", boolValue=False)
    STATUS_WAITING_FOR_DEPENDENCIES = Constant(strValue="Waiting", boolValue=False)
    STATUS_ABNORMAL_SHUTDOWN        = Constant(strValue="Abnormal Shutdown", boolValue=False)
    STATUS_ENABLED                  = Constant(strValue="Enabled", boolValue=True)
    
    REGISTER_DEVICE_TYPE_NAME = None # All abstract classes should leave this none. All concrete classes must specify.
    
    def __init__(self, deviceName, ):
        self._pnms = None
        self._config = None
        self._name = deviceName
        self._deviceDependencies = set([])
        
        # the status is the current status
        self._enableStatus = self.STATUS_DISABLED
        # the toggle is if there has been a request to go from one state to the other
        self._enableToggle = False
        
    def installToNetwork(self, pnms, mySection):
        self._pnms = pnms
        self._config = mySection
        # call self.enabled to correctly set enableStatus
        # cannot call in constructor, requires self._pnms
        self._runEnableStatusStateMachine()
        
    def networkManager(self):
        return self._pnms
        
    def _sanitizeVerb(self, verb):
        return verb.strip().lower()
        
    def name(self):
        return self._name
        
    def dependenciesEnabled(self):
        for device in self._deviceDependencies:
            if not device.enabled(): return False
        return True
        
    def isAutoEnabled(self):
        return self._config.get(self.CONFIG_OPTION_AUTO, self.CONFIG_FALSE) == self.CONFIG_TRUE
        
    def pnmsAlert(self, device, alert, alertArgs):
        if device in self._deviceDependencies:
            if alert == device.enabled:
                self._runEnableStatusStateMachine()
        
    def initialize(self, args):
        pass
        
    def destroy(self):
        pass
        
    def enable(self):
        if not self.enabled():
            self._enableToggle = True
            self._runEnableStatusStateMachine()
        
    def disable(self):
        if self.enabled():
            self._enableToggle = True
            self._runEnableStatusStateMachine()
        
    def enabled(self):
        return self._enableStatus
        
    def getPid(self):
        statusFile, pidFile, lockFile = self._getDeviceRunFiles()
        if os.path.exists(pidFile):
            with open(pidFile) as f:
                return int(f.read().strip())
        return None
        
    def config(self, verb, args):
        pass
        
    def _getDeviceRunFiles(self):
        statusFile = os.path.join(self._pnms.location(), "device_{}.status".format(self.name()))
        pidFile = os.path.join(self._pnms.location(), "device_{}.pid".format(self.name()))
        lockFile = os.path.join(self._pnms.location(), "device_{}.pid.lock".format(self.name()))
        
        return statusFile, pidFile, lockFile
        
    def _running(self):
        for requiredFile in self._getDeviceRunFiles():
            if not os.path.exists(requiredFile):
                return False
        pid = self.getPid()
        return pid and isPidAlive(pid)
        
    def _runEnableStatusStateMachine(self):
        newStatus = self._enableStatus
        
        # TODO: I wrote this function in a 'haze' thinkin the manager keeps running.
        # but, of course, it shuts down after run. There's going to be
        # no callback. Well, I'm leaving this code in. Because, it may
        # be that in the future I have a call-back system that works.
        # but for now, let's try to activate everything.
        if self._enableStatus == self.STATUS_WAITING_FOR_DEPENDENCIES:
            for device in self._deviceDependencies:
                if not device.enabled():
                    device.enable()
        
        if self._enableStatus in [self.STATUS_DISABLED, self.STATUS_ABNORMAL_SHUTDOWN]:
            if self._running():
                # We might have gotten here because of a restart
                # or a toggle.
                if self.dependenciesEnabled():
                    newStatus = self.STATUS_ENABLED
                else:
                    # oops. A dependency has shut down.
                    # Assume this device was supposed to be enabled.
                    self._shutdown()
                    newStatus = self.STATUS_WAITING_FOR_DEPENDENCIES
            elif self._enableToggle:
                if self.dependenciesEnabled():
                    self._launch()
                    if self._running():
                        newStatus = self.STATUS_ENABLED
                    else:
                        newStatus = self.STATUS_ABNORMAL_SHUTDOWN
            else: 
                newStatus = self.STATUS_DISABLED
        elif self._enableStatus == self.STATUS_WAITING_FOR_DEPENDENCIES:
            if self._enableToggle:
                # we were trying to turn on, were waiting for deps, but now stop
                newStatus = self.STATUS_DISABLED
            elif self.dependenciesEnabled():
                self._launch()
                if self._running():
                    newStatus = self.STATUS_ENABLED
                else: 
                    newStatus = self.STATUS_ABNORMAL_SHUTDOWN
            else:
                newStatus = self.STATUS_WAITING_FOR_DEPENDENCIES
        elif self._enableStatus == self.STATUS_ENABLED:
            if self._enableToggle:
                self._shutdown()
                newStatus = self.STATUS_DISABLED
            elif not self._running():
                newStatus = self.STATUS_DISABLED
            elif not self.dependenciesEnabled():
                self._shutdown()
                newStatus = self.STATUS_WAITING_FOR_DEPENDENCIES
            else:
                newStatus = self.STATUS_ENABLED
        alert = (self._enableStatus != newStatus)
        self._enableStatus = newStatus
        self._enableToggle = False
        self._pnms.postAlert(self.enable, self._enableStatus)
        
    def _shutdown(self, timeout=5):
        pid = self.getPid()
        if pid:
            os.kill(pid, signal.SIGTERM)
            sleepCount = timeout
            while isPidAlive(pid) and sleepCount > 0:
                time.sleep(1)
                sleepCount = sleepCount-1
            if isPidAlive(pid):
                raise Exception("Could not shut down device {}. (pid={})".format(self.name(), pid))
        for file in self._getDeviceRunFiles():
            if os.path.exists(file):
                os.unlink(file)
                
    def _launch(self, timeout=30):
        pass
        
    def _waitUntilRunning(self, timeout=30):
        sleepCount = timeout
        while not self._running() and sleepCount > 0:
            time.sleep(1)
            sleepCount = sleepCount - 1
        return self._running()
        