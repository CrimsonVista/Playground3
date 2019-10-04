'''
Created on Oct 11, 2017

@author: seth_
'''

from .AbstractStreamAdapter import AbstractStreamAdapter

import struct, zlib
from io import SEEK_END, SEEK_CUR, SEEK_SET

import logging
logger = logging.getLogger("playground.packetfraemstreamadapter")

class PacketFramingStreamAdapter(AbstractStreamAdapter):
    """
    This Stream reads and writes framed bytes. 
    
    A framed stream starts with the 4-byte sequence:
    
    0x 05 08 0D 15
    
    This is followed by a total size X, and a 4-byte checksum
    over the 4-byte sequence and X: CRC32(MAGIC + X).
    
    The end of the stream if terminated with CRC32(X + REV_MAGIC)
    X, and REV_MAGIC which is the reverse of the magic number
    
    0x 51 D0 80 50
    
    If the stream does not conform, it will raise an exception
    after skipping ahead to a new magic sequence, or to the end
    of the stream.
    
    So, each frame is
    
    [ MAGIC(4) ] [ X (4) ] [ CRC1(4) ] [ X BYTES ] [ CRC2(4) ] [ X(4) ] [ REV_MAGIC (4) ]
    """
    
    MAGIC = b"\x05\x08\x0D\x15"
    REV_MAGIC = b"\x51\xD0\x80\x50"
    
    PREFIX_SIZE = 12
    SUFFIX_SIZE = 12
        
    def __init__(self, stream):
        self._stream = stream
        self._prefixStart = stream.tell()
        self._startChecked = False
        self._endChecked = False
        self._checkStreamStart()
        self._checkStreamEnd()
        
    def _fail(self, errMsg):
        #if self._startChecked:
        #    self.seek(self._dataSize)
        #logger.debug("Packet stream failed {}".format(errMsg))
        #logger.debug("stream location after seek data size is {}".format(self._stream.tell()))
        while self._rawAvailable() >= len(self.MAGIC) and self._stream.peek(4) != self.MAGIC:
            #logger.debug("{} {} {} {}".format(self._stream.peek(4),"doesn't match",self.MAGIC,"so advance 1"))
            self._stream.read(1)
        raise Exception(errMsg)
    
    def _rawStreamSize(self):
        curPos = self._stream.tell()
        self._stream.seek(0, SEEK_END)
        endPos = self._stream.tell()
        self._stream.seek(curPos)
        return endPos - self._prefixStart
        
    def _rawAvailable(self):
        "some underlying streams may not support 'available'"
        curPos = self._stream.tell()
        self._stream.seek(0, SEEK_END)
        endPos = self._stream.tell()
        self._stream.seek(curPos)
        return endPos - curPos
        
    def _checkStreamStart(self):
        if self._startChecked:
            return
        
        # ok, we've not started yet, either read or write. Start back at prefix start
        # the way "tell()/seek()" is written, we might have gotten moved, so we have to reset
        self._stream.seek(self._prefixStart)
        if self._rawAvailable() < self.PREFIX_SIZE:
            self._dataSize = None
        else:
            prefix = self._stream.peek(self.PREFIX_SIZE)
            magic, sizeBytes, checkBytes = prefix[:4], prefix[4:8], prefix[8:12] 
            if magic != self.MAGIC:
                self._fail("Bad Magic Number at Start")
            check = zlib.adler32(magic)
            size = struct.unpack("!I",sizeBytes)[0]
            check = zlib.adler32(sizeBytes, check)
            
            cmpCheck = struct.unpack("!I", checkBytes)[0]
            if cmpCheck != check:
                self._fail("Bad Prefix Checksum")
            
            # only if we get this far do we actually read out the bytes from the stream
            self._stream.read(self.PREFIX_SIZE)    
            self._dataSize = size
            self._startChecked = True
            
    def _checkStreamEnd(self):
        if self._dataSize == None: return
        elif self._endChecked: return
        elif self._rawStreamSize() >= (self.PREFIX_SIZE + self._dataSize + self.SUFFIX_SIZE):
            # we now have the ending of the frame.
            
            curPos = self._stream.tell()
            self._stream.seek(self._prefixStart + self.PREFIX_SIZE + self._dataSize)
            
            checkBytes = self._stream.read(4)
            cmpCheck = struct.unpack("!I", checkBytes)[0]
            
            sizeBytes = self._stream.read(4)
            size = struct.unpack("!I",sizeBytes)[0]
            
            if size != self._dataSize:
                self._fail("Suffix Size Mismatch")
            
            magic = self._stream.read(4)
            if magic != self.REV_MAGIC:
                self._fail("Bad Magic Number at End")
            check = zlib.adler32(sizeBytes)
            check = zlib.adler32(magic, check)
            
            if cmpCheck != check:
                self._fail("Bad Suffix Checksum")
                
            self._stream.seek(curPos)
            self._endChecked = True
      
    def available(self):
        """
        Get the available bytes, cutting off the suffix if
        it's been acocunted for
        """
        if not self._rawStreamSize() >= (self.PREFIX_SIZE + self.SUFFIX_SIZE):
            return 0
        curPos = self._stream.tell()
        # even if the suffix hasn't been received yet, we calculate our offsets as if it had.
        # why? because if it hasn't been received yet, we don't want to finish! The whole packet
        # isn't framed (verified) until the final bytes are received.
        self._stream.seek(-self.SUFFIX_SIZE, SEEK_END)
        endPos = self._stream.tell()
        self._stream.seek(curPos)
        return endPos-curPos
        
    def seek(self, offset, whence=SEEK_SET):
        "Adjust seek from prefix start and, if present, from prefix"
        if not self._rawStreamSize() >= (self.PREFIX_SIZE + self.SUFFIX_SIZE):
            return
        if whence == SEEK_SET:
            offset += self._prefixStart + self.PREFIX_SIZE
            return self._stream.seek(offset, whence)
        elif whence == SEEK_CUR:
            return self._stream.seek(offset, whence)
        elif whence == SEEK_END:
            # even if the suffix hasn't been received yet, we calculate our offsets as if it had.
            # why? because if it hasn't been received yet, we don't want to finish! The whole packet
            # isn't framed (verified) until the final bytes are received.
            offset = offset - self.SUFFIX_SIZE
            return self._stream.seek(offset, whence)
        
    def tell(self, *args):
        "Adjust seek from prefix start and, if present, from prefix"
        if self._rawStreamSize() < (self.PREFIX_SIZE + self.SUFFIX_SIZE):
            return 0
        curPos = self._stream.tell(*args)
        curPos = curPos - self._prefixStart
        curPos = curPos - self.PREFIX_SIZE
        if curPos < 0:
            curPos = 0
        return curPos
        
    def read(self, count):
        self._checkStreamStart()
        self._checkStreamEnd()
        if not self._startChecked:
            self._fail("No frame data. Cannot read.")
            
        readMinIndex = self._prefixStart+self.PREFIX_SIZE
        readMaxIndex = readMinIndex + self._dataSize
        if not self._endChecked:
            curPos = self._stream.tell()
            self._stream.seek(-1,SEEK_END)
            readMaxIndex = self._stream.tell()
            self._stream.seek(curPos)
            
        readStart = self._stream.tell()
        
        if readStart < readMinIndex or readStart > readMaxIndex:
            raise Exception("We tried to read at {} (range is {}/{})".format(readStart, readMinIndex, readMaxIndex))
            return b""
        if count > self.available():
            if count == 1: raise Exception("Tried to read 1 byte but can't because not enough size?")
            count = self.available()
        return self._stream.read(count)
        
    def write(self, data):
        if self._endChecked:
            raise Exception("Frame data already in place. Cannot write")
        if not self._startChecked:
            """
            OK. This is apparently a writer. This adapter really wasn't meant for mix and match.
            Should we throw an error if not at the beginning?
            
            TODO: Errors on switch between read and write?
            """
            if not self._stream.tell() <= (self._prefixStart + self.PREFIX_SIZE):
                # we're not at the beginning. This shouldn't happen. Can't write until we've written the prefix
                raise Exception("First write was not at the beginning of the buffer")
            
            self._stream.seek(self._prefixStart)
            # set startChecked to True so that we're done from here on out.
            self._startChecked = True
            self._dataSize = 0
            
            """
            OK, at beginning of write, put in magic number 3 times. Once at the beginning for real,
            and the other two times as dummy values for placeholders for length and checksum.
            """
            self._stream.write(self.MAGIC)
            self._stream.write(self.MAGIC)
            self._stream.write(self.MAGIC)
        ret = self._stream.write(data)
        curPos = self._stream.tell()
        estSize = curPos - self._prefixStart - self.PREFIX_SIZE
        if estSize > self._dataSize:
            self._dataSize = estSize
    
    def writeFrame(self):
        if self._endChecked:
            raise Exception("Cannot write frame data. Already present")
        
        self._stream.seek(self._prefixStart+4)
        check = zlib.adler32(self.MAGIC)
        sizeBytes = struct.pack("!I",self._dataSize)
        check = zlib.adler32(sizeBytes, check)
        self._stream.write(sizeBytes)
        self._stream.write(struct.pack("!I",check))
        
        self._stream.seek(self._prefixStart + self.PREFIX_SIZE + self._dataSize)
        
        check = zlib.adler32(sizeBytes)
        check = zlib.adler32(self.REV_MAGIC, check)
        self._stream.write(struct.pack("!I", check))
        self._stream.write(sizeBytes)
        self._stream.write(self.REV_MAGIC)
        
        self._endChecked = True
        
    def closeFrame(self):
        """
        We're done reading from this frame. Advance the read pointer
        past the ending data
        """
        if not self._endChecked:
            self._fail("End not yet reached.")
        self._stream.seek(self._prefixStart+self.PREFIX_SIZE+self._dataSize+self.SUFFIX_SIZE)
