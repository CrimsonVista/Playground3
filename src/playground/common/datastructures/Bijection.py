from collections.abc import MutableMapping

def mutable(f):
    def newF(self, *args, **kargs):
        if self.immutable():
            raise TypeError("Invalid operation '%s' on immutable object" % f.__name__)
        return f(self, *args, **kargs)
    return newF

class Bijection(MutableMapping):
    """
    A Bijection maps elements of a first set to elements
    of a second set in a one-to-one correspondence. An
    insertion of (a,b) will map a to b and b to a, replacing
    any previously existing mapping of a or b.
    
    The mapping supports __setitem__ and __getitem__, and these
    set in the "forward" direction from the first set to the
    second set. To lookup in the reverse direction,
    the method "inverse()" returns a Bijection in the opposite
    direction. The method "inverseMutable()" returns
    an inverse map that can set values (but with the direction reversed).
    
    b = bijection()
    bInv = b.inverse()
    b['a'] = 1
    b['a'] # maps to 1
    b['b'] = 10
    
    bInv[1]      # maps to 'a'
    bInv[10]     # maps to 'b'
    
    b['c'] = 10
    bInv[10]     # maps to 'c', not b
    b['b']       # ERROR 'b' was unmapped!
    bInv[10]='b' # ERROR, bInv immutable
    
    b.inverseMutable()[10]='c'
"""
    __ConstructorGuard = False
    
    def __init__(self):
        self.__forward = {}
        self.__reverse = {}
        self.__immutable = False
        self.__inverse = object.__new__(self.__class__)
        self.__inverseMutable = object.__new__(self.__class__)
        
        # we already have self, __inverse, and __inverseMutable. But we'll
        # also need an immutable version of our self for our inverses to point to.
        immutableSelf = object.__new__(self.__class__)
        
        self.__inverse.__immutable = True
        self.__inverseMutable.__immutable = False
        immutableSelf.__immutable = True
        
        # start with the mutable inverse
        self.__inverseMutable.__forward = self.__reverse
        self.__inverseMutable.__reverse = self.__forward
        self.__inverseMutable.__inverseMutable = self
        self.__inverseMutable.__inverse = immutableSelf
        
        # setup immutable version of self
        # no need to set inverseMutable; immutable objects can't access it
        immutableSelf.__forward = self.__forward
        immutableSelf.__reverse = self.__reverse
        immutableSelf.__inverse = self.__inverse
        immutableSelf.__inverseMutable = None
        
        # setup immutable inverse
        # no need to set inverseMutable; immutable objects can't access it
        self.__inverse.__forward = self.__reverse
        self.__inverse.__reverse = self.__forward
        self.__inverse.__inverse = immutableSelf
        self.__inverse.__inverseMutable = None
        
    def __getitem__(self, k):
        return self.__forward[k]
        
    def __len__(self):
        return len(self.__forward)
        
    def __iter__(self):
        return self.__forward.__iter()
    
    @mutable
    def __setitem__(self, k, v):
        if k in self.__forward:
            deadValue = self.__forward[k]
            del self.__reverse[deadValue]
        if v in self.__reverse:
            deadKey = self.__reverse[v]
            del self.__forward[deadKey]
        self.__forward[k] = v
        self.__reverse[v] = k
    
    @mutable
    def __delitem__(self, k):
        del self.__reverse[self.__forward[k]]
        del self.__forward[k]
        
    def inverse(self):
        return self.__inverse
    
    @mutable
    def inverseMutable(self):
        return self.__inverseMutable
        
    def immutable(self):
        return self.__immutable
        
def basicUnitTest():
    b = Bijection()
    bInv = b.inverse()
    b['a'] = 1
    assert(b['a']==1) 
    b['b'] = 10
    assert(b['b']==10)
    
    assert(bInv[1]=='a')
    assert(bInv[10]=='b')
    
    assert(len(b) == len(bInv))
    
    b['c'] = 10
    assert(bInv[10]=='c')
    try:
        b['b']  # ERROR 'b' was unmapped!
        assert False, "Should raise a KeyError"
    except KeyError:
        assert(True)
        
    try:
        bInv[10]='b' # ERROR, bInv immutable
        assert False, "Should raise a TypeError"
    except TypeError:
        assert(True)
        
    try:
        del bInv[10]
        assert False, "Should raise a TypeError"
    except TypeError:
        assert(True)
    
    try:
        bInv.inverseMutable()
        assert False, "Should raise a TypeError"
    except TypeError:
        assert(True)
    
    del b['a']
    assert('a' not in b)
    assert(1 not in bInv)
    
    b.inverseMutable()[10]='c'
    assert(b['c']==10)
    del b.inverseMutable()[10]
    assert(10 not in b.inverseMutable())
    assert('c' not in b)
    
if __name__=="__main__":
    basicUnitTest()