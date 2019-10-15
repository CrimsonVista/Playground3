from playground.common.datastructures import HierarchicalDictionary
from playground.common import CustomConstant
from playground.common import Version as PacketDefinitionVersion

class PacketDefinitionRegistration(object):
    class DefinitionPOD(object):
        
        def __init__(self):
            self.versions = {}
            self.majorMax = 0
            self.minorMax = {0:0}
    
    MOST_RECENT = CustomConstant(strValue="MOST RECENT")
            
    def __init__(self):
        self.__definitions = HierarchicalDictionary()
    
    def getDefinition(self, identifier, version=MOST_RECENT, permitCompatible=False):
        definitionData = self.__definitions.get(identifier, None)
        if not definitionData or not definitionData.versions: return None
        
        if version == self.MOST_RECENT:
            version = PacketDefinitionVersion(definitionData.majorMax, definitionData.minorMax[definitionData.majorMax])
        if version in definitionData.versions:
            return definitionData.versions[version]

        if findCompatibleVersion:
            if version.major in definitionData.minorMax:
                compatibleVersion = PacketDefinitionVersion(version.major, definitionData.minorMax[version.major])
                return definitionData.versions[compatibleVersion]
        return None        
        
    def hasDefinition(self, identifier, version=MOST_RECENT):
        definition = self.getDefinition(identifier, version)
        return definition != None
        
    def registerDefinition(self, identifier, version, definition):
        definitionData = self.__definitions.get(identifier, self.DefinitionPOD())
        definitionData.versions[version] = definition
        definitionData.majorMax = max(version.major, definitionData.majorMax)
        definitionData.minorMax[version.major] = max(definitionData.minorMax.get(version.major, 0), version.minor)
        self.__definitions[identifier] = definitionData
        
    def unregisterDefinition(self, identifier):
        if identifier in self.__definitions:
            del self.__definitions[identifier]
        
    def __iter__(self):
        return self.__definitions.__iter__()



class PacketDefinitionSilo:
    """
    This class is a context manager that, while "entered" records
    all packets to a different "g_DefaultPacketDefinitions". When
    closed, the default is restored.
    """
    
    SILOS = {"__default__":PacketDefinitionRegistration()}
    STACK = [SILOS["__default__"]]
    AUTO_NAME = ("__unnamed__{}".format(x) for x in range(1000000))
    
    @classmethod
    def CurrentSilo(cls):
        return cls.STACK[-1]
    
    @classmethod
    def GetSiloByName(cls, siloName):
        if siloName == "__current_silo__": return cls.CurrentSilo()
        return cls.SILOS.get(siloName, None)
    
    def __init__(self, name=None, reuse=False):
        if name == None:
            name = next(self.AUTO_NAME)
        if name in self.SILOS:
            if not reuse:
                raise Exception("Cannot have a duplicate name for a silo unless reuse=True")
        else:
            self.SILOS[name] = PacketDefinitionRegistration()
            
        self.name = name
        
    def __enter__(self):
        self.STACK.append(self.SILOS[self.name])
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.STACK.pop(-1)
    