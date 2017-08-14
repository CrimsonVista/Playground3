from collections.abc import MutableMapping

class HierarchicalKeyHandler(object):
    """
    HierarchicalKeyHandler is an abstract class (interface) with
    two methods: split and join. Implementing classes should define
    split and join for data such that split(data) produces a list
    of parts and join(parts) produce the original data.
    
    join(split(data)) = data
    """
    def split(self, key):
        raise NotImplementedError
        
    def join(self, keyParts):
        raise NotImplementedError

class HierarchicalDictionary(MutableMapping):
    """
    HierarchicalDictionary maps hierarcical keys to data, 
    where the key hierarchy is determined by the key handler.
    The default key handler requires that data supports a 
    'split' method, e.g., strings.
    
    d['x'] = 1
    d['x.a'] = 2
    """
    
    class DEFAULT_KEY_HANDLER(HierarchicalKeyHandler):
        def split(self, key):
            return key.split(".")
        def join(self, keyParts):
            return ".".join(keyParts)
            
    def __init__(self, splitter=None):
        self._splitter = splitter
        if not self._splitter:
            self._splitter = self.DEFAULT_KEY_HANDLER()
        self._subDicts = {}
        self._terminals = {}
        
    def lookupByKeyParts(self, keyParts):
        if len(keyParts) == 1:
            return self._terminals[keyParts[0]]
        elif len(keyParts) == 0:
            raise KeyError
        else:
            if keyParts[0] not in self._subDicts:
                raise KeyError
            return self._subDicts[keyParts[0]].lookupByKeyParts(keyParts[1:])
            
    def storeByKeyParts(self, keyParts, value):
        if len(keyParts) == 1:
            self._terminals[keyParts[0]] = value
        elif len(keyParts) == 0:
            raise KeyError
        else:
            if keyParts[0] not in self._subDicts:
                self._subDicts[keyParts[0]] = HierarchicalDictionary(splitter=self._splitter)
            self._subDicts[keyParts[0]].storeByKeyParts(keyParts[1:], value)
            
    def deleteByKeyParts(self, keyParts):
        if len(keyParts) == 1:
            del self._terminals[keyParts[0]]
        elif len(keyParts) == 0:
            raise KeyError
        else:
            self._subDicts[keyParts[0]].deleteByKeyParts(keyParts[1:])
            if len(self._subDicts[keyParts[0]]) == 0:
                del self._subDicts[keyParts[0]]
                
    def iterKeys(self, parentKeys=None):
        for key in self._terminals.keys():
            if parentKeys:
                yield self._splitter.join(parentKeys+[key])
            else:
                yield key
        for subKey in self._subDicts.keys():
            if parentKeys:
                for hierarchicalKey in self._subDicts[subKey].iterKeys(parentKeys+[subKey]):
                    yield hierarchicalKey
            else:
                for hierarchicalKey in self._subDicts[subKey].iterKeys([subKey]):
                    yield hierarchicalKey
        
    def __getitem__(self, key):
        subKeys = self._splitter.split(key)
        return self.lookupByKeyParts(subKeys)
        
    def __setitem__(self, key, value):
        subKeys = self._splitter.split(key)
        self.storeByKeyParts(subKeys, value)
    
    def __delitem__(self, key):
        subKeys = self._splitter.split(key)
        self.deleteByKeyParts(subKeys)
        
    def __len__(self):
        count = len(self._terminals)
        for subKey in self._subDicts.keys():
            count += len(self._subDicts[subKey])
        return count
        
    def __iter__(self):
        return self.iterKeys()
        
def basicUnitTest():
    hd = HierarchicalDictionary()
    hd["a"] = 1
    hd["a.x"] = 2
    hd["a.x.k"] = 3
    assert(hd["a"] == 1)
    assert(hd["a.x"] == 2)
    assert(hd["a.x.k"] == 3)
    assert(len(hd) == 3)
    keys = []
    for k in hd:
        keys.append(k)
    assert("a" in keys)
    assert("a.x" in keys)
    assert("a.x.k" in keys)
    del hd["a.x"]
    assert("a" in hd)
    assert("a.x" not in hd)
    assert("a.x.k" in hd)
    
if __name__=="__main__":
    basicUnitTest()
    print("Basic Unit Test Passed.")