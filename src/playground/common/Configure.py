'''
Created on Oct 1, 2017

@author: seth_
'''
import playground
import os
import configparser
import time

class Configure:
    if "PLAYGROUND_INSTANCE" in os.environ:
        INSTANCE_CONFIG_PATH = os.path.join(os.environ["PLAYGROUND_INSTANCE"], ".playground")
    else:
        INSTANCE_CONFIG_PATH = None
    USER_CONFIG_PATH    = "~/.playground"
    SYSTEM_CONFIG_PATH   = "/var/playground"
    
    INSTANCE_CONFIG_KEY = "INSTANCE"
    USER_CONFIG_KEY    = "USER"
    SYSTEM_CONFIG_KEY   = "SYSTEM"
    
    SEARCH_PATHS = {INSTANCE_CONFIG_KEY   :INSTANCE_CONFIG_PATH,
                    USER_CONFIG_KEY       :USER_CONFIG_PATH, 
                    SYSTEM_CONFIG_KEY     :SYSTEM_CONFIG_PATH}
    
    SEARCH_ORDER = [USER_CONFIG_KEY, SYSTEM_CONFIG_KEY]
    if INSTANCE_CONFIG_PATH:
        SEARCH_ORDER.insert(0, INSTANCE_CONFIG_KEY)
    
    CONFIG_MODULES = []
    
    @classmethod
    def ConfigPath(cls, pathId):
        """
        This function can be used to initialize a playground network
        management config file (empty).
        """
        location = cls.SEARCH_PATHS[pathId]
        if pathId == cls.INSTANCE_CONFIG_KEY and location == None:
            raise Exception("Cannot initialize playground. PLAYGROUND_INSTANCE unconfigured.")
        location = os.path.expanduser(location)
        return location
    
    @classmethod
    def CurrentPath(cls):
        for searchKey in cls.SEARCH_ORDER:
            searchLocation = cls.ConfigPath(searchKey)
            if searchLocation and os.path.exists(searchLocation):
                return searchLocation
        raise Exception("No configure path found.")
    
    @classmethod
    def Initialize(cls, pathId, overwrite=False):
        location = cls.ConfigPath(pathId)
        if not os.path.exists(location):
            os.mkdir(location)
            
        for module in cls.CONFIG_MODULES:
            module.InitializeConfigModule(location, overwrite)
            
    @classmethod
    def AddCustomPath(cls, customPathId, customPath):
        if customPathId in cls.SEARCH_PATHS:
            raise Exception("Duplicate path id {}".format(customPathId))
        cls.SEARCH_PATHS[customPathId] = customPath
        cls.SEARCH_ORDER = [customPathId] + cls.SEARCH_ORDER
        
class PlaygroundConfigFile:
    @classmethod
    def Exists(cls, identifier, location=None):
        if location==None:
            location = Configure.CurrentPath()
        path_parts = [location] + identifier.split(".")
        path = os.path.join(*path_parts)+".ini"
        return os.path.exists(path)
        
    @classmethod
    def Open(cls, identifier, access="read", create="", location=None, **spec):
        if access not in ["read","write"]:
            raise Exception("Unknown access mode {}".format(access))
        if create not in ["", "overwrite", "ifneeded"]:
            raise Exception("Unknown creation mode {}".format(create))
        if location==None:
            location = Configure.CurrentPath()
        path_parts = [location] + identifier.split(".")
        path = os.path.join(*path_parts)+".ini"
        if (not os.path.exists(path) and create=="ifneeded") or create == "overwrite":
            os.mkdirs(os.path.dirname(path))
            with open(path,"w+") as f:
                f.write("# Playground Config {} Created {}\n\n".format(
                    identifier,
                    time.asctime()
                ))
        if not os.path.exists(path):
            raise Exception("No such config file {}.".format(identifier))
        return cls(identifier, access, path, spec)
        
    def __init__(self, identifier, access, path, spec):
        self._identifier = identifier
        self._access = access
        self._path = path
        self._spec = spec
        self._modtime = time.time()
        self.reload(force=True)
        
    def identifier(self):
        return self._identifier
        
    def access(self):
        return self._access
        
    def path(self):
        return self._path
        
    def __enter__(self):
        return self
        
    def __exit__(self):
        if self._access in ["write"]:
            self.save()
            
    def reload(self, force=False):
        newLastModifiedTime = os.path.getmtime(self._path)
        if newLastModifiedTime > self._modtime or force:
            self._config = configparser.ConfigParser()
            self._config.read(self._path)
            for sec in self._spec:
                if sec not in self._config:
                    self._config[sec] = self._spec[sec]
                
    def save(self):
        if self._access not in ["write"]:
            raise Exception("Cannot save a read-only config.")
        with open(self._path, 'w+') as configfile:
            self._config.write(configfile)
                
    def __getitem__(self, key):
        return self._config[key]
        
    def __setitem__(self, key, value):
        self._config[key] = value
        
    def __contains__(self, key):
        return self._config.__contains__(key)