from playground.common.datastructures import HierarchicalDictionary
from playground.common import CustomConstant

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

g_DefaultPacketDefinitions = PacketDefinitionRegistration()
        