'''
Created on Oct 1, 2017

@author: seth_
'''
import playground
import os

class Configure:
    INSTANCE_CONFIG_PATH = os.path.join(playground.STARTUP_DIR, ".playground")
    LOCAL_CONFIG_PATH    = "~/.playground"
    GLOBAL_CONFIG_PATH   = "/var/playground"
    
    INSTANCE_CONFIG_KEY = "INSTANCE"
    LOCAL_CONFIG_KEY    = "LOCAL"
    GLOBAL_CONFIG_KEY   = "GLOBAL"
    
    SEARCH_PATHS = {INSTANCE_CONFIG_KEY    :INSTANCE_CONFIG_PATH,
                    LOCAL_CONFIG_KEY       :LOCAL_CONFIG_PATH, 
                    GLOBAL_CONFIG_KEY      :GLOBAL_CONFIG_PATH}
    
    SEARCH_ORDER = [INSTANCE_CONFIG_KEY, LOCAL_CONFIG_KEY, GLOBAL_CONFIG_KEY]
    
    CONFIG_MODULES = []
    
    @classmethod
    def ConfigPath(cls, pathId):
        """
        This function can be used to initialize a playground network
        management config file (empty).
        """
        location = cls.SEARCH_PATHS[pathId]
        location = os.path.expanduser(location)
        return location
    
    @classmethod
    def CurrentPath(cls):
        for searchKey in cls.SEARCH_ORDER:
            searchLocation = cls.ConfigPath(searchKey)
            if os.path.exists(searchLocation):
                return searchLocation
        raise Exception("No configure path found.")
    
    @classmethod
    def Initialize(cls, pathId, overwrite=False):
        location = cls.ConfigPath(pathId)
        if not os.path.exists(location):
            os.mkdir(location)
            
        for module in cls.CONFIG_MODULES:
            module.InitializeConfigModule(location, overwrite)