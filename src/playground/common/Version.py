

class Version(object):
    @classmethod
    def FromString(cls, vString):
        vParts = vString.split(".")
        if len(vParts) != 2:
            raise AttributeError("Packet Definition Version must be of the form 'x.y'")
        try:
            major, minor = map(int, vParts)
        except:
            raise AttributeError("Packet Definition Version must be composed of integers")
        return cls(major, minor)
        
    def __init__(self, major, minor):
        assert(isinstance(major, int))
        assert(isinstance(minor, int))
        
        self.major = major
        self.minor = minor
        
    def __str__(self):
        return "%d.%d" % (self.major, self.minor)
        
    def __eq__(self, otherVersion):
        if not isinstance(otherVersion, Version):
            return False
        return self.major == otherVersion.major and self.minor == otherVersion.minor
        
    def __hash__(self):
        return hash((self.major, self.minor))