'''
Created on Oct 1, 2017

@author: seth_
'''
import playground
import os

class Configure:
    if "PLAYGROUND_INSTANCE" in os.environ:
        INSTANCE_CONFIG_PATH = os.path.join(os.environ["PLAYGROUND_INSTANCE"], ".playground")
    else:
        INSTANCE_CONFIG_PATH = None
    LOCAL_CONFIG_PATH    = "~/.playground"
    GLOBAL_CONFIG_PATH   = "/var/playground"
    
    INSTANCE_CONFIG_KEY = "INSTANCE"
    LOCAL_CONFIG_KEY    = "LOCAL"
    GLOBAL_CONFIG_KEY   = "GLOBAL"
    
    SEARCH_PATHS = {INSTANCE_CONFIG_KEY    :INSTANCE_CONFIG_PATH,
                    LOCAL_CONFIG_KEY       :LOCAL_CONFIG_PATH, 
                    GLOBAL_CONFIG_KEY      :GLOBAL_CONFIG_PATH}
    
    SEARCH_ORDER = [LOCAL_CONFIG_KEY, GLOBAL_CONFIG_KEY]
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