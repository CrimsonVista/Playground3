'''
Created on September 10, 2017

Original File creates Dec 5, 2013

@author: sethjn
'''

import logging, logging.handlers
import random, os, sys
from argparse import Action

class TaggedLogger(object):
    TAG_KEY = "__playlogtag__"
        
    
    @classmethod
    def GetTag(cls, loggerName):
        parts = loggerName.split(".")
        if parts[-1].startswith(cls.TAG_KEY):
            return parts[-1][len(cls.TAG_KEY):]
        return ""
    
    @classmethod
    def GetTaggedLoggerName(cls, baseLoggerName, tag):
        return ".".join([baseLoggerName, cls.TAG_KEY+tag])
    
    @classmethod
    def GetTaggedLoggerNameForObject(cls, obj, tag):
        return cls.GetTaggedLoggerName(".".join([obj.__module__, obj.__class__.__name__]), tag)
        

class PlaygroundLoggingFilter(logging.Filter):
    LOG_ALL_MODULES = 'global'
    LOG_ALL_TAGS = 'verbose'
    
    def __init__(self, logModules=LOG_ALL_MODULES, logTags=LOG_ALL_TAGS):
        self.configure(logModules, logTags)
        
    def configure(self, logModules=LOG_ALL_MODULES, logTags=LOG_ALL_TAGS):
        if logModules == self.LOG_ALL_MODULES or not logModules:
            self.globalLogging = True
            self.moduleLogging = []
        else:
            self.globalLogging = False
            self.moduleLogging = logModules
            
        self.tagLogging = logTags

    def logThisTag(self, tagName):
        if self.tagLogging == self.LOG_ALL_TAGS or not tagName: return True
        if not self.tagLogging: return False
        return tagName in self.tagLogging
        
    def logThisLogger(self, loggerName):
        loggerTag = TaggedLogger.GetTag(loggerName)
        
        if self.globalLogging: 
            return self.logThisTag(loggerTag)
        for loggedModuleName in self.moduleLogging:
            if loggerName.startswith(loggedModuleName):
                
                return self.logThisTag(loggerTag)
        return False
    
    def filter(self, record):
        return self.logThisLogger(record.name)

class PartialConverter(object):
    def __init__(self, d):
        self.d =d 
        
    def __getitem__(self, k):
        if k in self.d: return self.d[k]
        return "%("+k+")s"

class PlaygroundLoggingFormatter(logging.Formatter):
    SPECIAL_CONVERTERS = {}
    def __init__(self, fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"):
        logging.Formatter.__init__(self, fmt)
        
    def format(self, record):
        if hasattr(record, '__playground_special__'):
            converters = {}
            for dataKey, specialData in record.__playground_special__.items():
                converters[dataKey] = self.SPECIAL_CONVERTERS[dataKey](specialData)
            record.msg = record.msg % PartialConverter(converters)
        return super(PlaygroundLoggingFormatter, self).format(record)
        

class PlaygroundLoggingConfiguration(logging.Handler):
    
    PLAYGROUND_ROOT_LOGGER = "playground"
    
    STDERR_HANDLER = logging.StreamHandler()
    
    # LOGFILE is defined in the singleton constructor
    
    def __init__(self):
        super(logging.Handler, self).__init__()
        self.loggingNode = sys.argv and str(sys.argv[0]) or "unknown playground_app"
        self.handlers = {}        
        # rootLogLevel is set every time enableLogging is called.
        # Logger logs everyting. We filter at the hander/filter level
        
    def toggleMaxLogging(self):
        raise Exception("Not yet implemented") 
        
    def handle(self, record):
        for handler in self.handlers:
            if record.levelno == logging.NOTSET or handler.level <= record.levelno:
                handler.handle(record)
            
    def enableLogging(self, logLevel=logging.NOTSET, rootLogging=False, additionalModules=None):
        "by default, turn all logging on and leave to handlers to filter"
        
        if rootLogging:
            rootLogger = ""
        else:
            rootLogger = self.PLAYGROUND_ROOT_LOGGER
            "Python is weird about 'NOTSET'. It enables everything at root, but"
            "for all other loggers, just propagates. So we'll just set it to '1' which"
            "is, I belive, the highest logging other than NOTSET"
            if logLevel == logging.NOTSET:
                logLevel = 1
        
        logging.getLogger(rootLogger).setLevel(logLevel)
        if self not in logging.getLogger(rootLogger).handlers:
            logging.getLogger(rootLogger).addHandler(self)
        if additionalModules:
            for module in additionalModules:
                logging.getLogger(module).setLevel(logLevel)
                logging.getLogger(module).addHandler(self)
            
        # this handler logs everyting, and then passes off to sub-handlers
        self.setLevel(logging.NOTSET)
    
    def enableHandler(self, handler, level=logging.DEBUG, specificModules=None, specificTags=None):
        #TODO: User should be able to configure formatter somehow, but it
        # needs to be a playground formatter.
        handler.setLevel(level)
        handler.setFormatter(PlaygroundLoggingFormatter())
        if handler not in self.handlers:
            pfilter = PlaygroundLoggingFilter(specificModules, specificTags)
            handler.addFilter(pfilter)
            self.handlers[handler] = pfilter
        else:
            pfilter = self.handlers[handler]
            pfilter.configure(specificModules, specificTags)
    
    def disableHandler(self, handler):
        if handler in self.handlers:
            handler.removeFilter(self.handlers[handler])
            del self.handlers[handler]
            
    def createRotatingLogFileHandler(self, name=None, path=None):
        if not path:
            localLogDirectory = os.expanduser("~/.playground/logs")
            if not os.path.exists(localLogDirectory):
                try:
                    os.path.makedirs(localLogDirectory)
                except:
                    localLogDirectory = os.getcwd()
        if not name:
            name = os.path.basename(self.loggingNode) +".log"
        return logging.handlers.TimedRotatingFileHandler(os.path.join(path, name))
        
        
Config = PlaygroundLoggingConfiguration() 

PRESET_MINIMAL = "MINIMAL"
PRESET_QUIET = "QUIET"
PRESET_VERBOSE = "VERBOSE"
PRESET_DEBUG = "DEBUG"
PRESET_TEST  = "TEST"
PRESET_MAX = "MAX"
PRESET_LEVELS = [PRESET_MINIMAL,
                 PRESET_QUIET,
                 PRESET_VERBOSE,
                 PRESET_DEBUG,
                 PRESET_TEST,
                 PRESET_MAX,
                 ]

def EnablePresetLogging(level, rootLogging=False):
    if level == PRESET_MINIMAL:
        # log error messages to logfile
        Config.enableLogging(rootLogging=rootLogging)
        Config.enableHandler(Config.createRotatingLogFileHandler(),logLevel=logging.ERROR)
    elif level == PRESET_QUIET:
        # logs most messages, but only to logfile
        Config.enableLogging(rootLogging=rootLogging)
        Config.enableHandler(Config.createRotatingLogFileHandler(), logLevel=logging.NOTSET)
    elif level == PRESET_VERBOSE:
        # logs all messages including those from asyncio, errors to stderr
        Config.enableLogging(additionalModules=["asyncio"],
                             rootLogging=rootLogging)
        Config.enableHandler(Config.STDERR_HANDLER, level=logging.ERROR)
        Config.enableHandler(Config.createRotatingLogFileHandler())
        # also prints to stderr
    elif level == PRESET_DEBUG:
        Config.enableLogging(additionalModules=["asyncio"],
                             rootLogging=rootLogging)
        Config.enableHandler(Config.STDERR_HANDLER, logLevel=logging.NOTSET)
        Config.enableHandler(Config.createRotatingLogFileHandler(), logLevel=logging.NOTSET)
        # Test is like debug, but doesn't log to a file.
    elif level == PRESET_TEST:
        Config.enableLogging(additionalModules=["asyncio"],
                             rootLogging=rootLogging)
        Config.enableHandler(Config.STDERR_HANDLER, level=logging.NOTSET)
    elif level == PRESET_MAX:
        raise Exception("Not yet implemented. Maybe will remove.")
    else:
        raise Exception("Unknown preset log level %s" % level)
    
def CmdLineToLogging(cmdLineArg):
    if cmdLineArg == "v"*len(cmdLineArg):
        EnablePresetLogging(PRESET_LEVELS[len(cmdLineArg)])
    else:
        EnablePresetLogging(cmdLineArg)
        
def ConfigureArgParser(parser, default="MINIMAL", rootLogging=False):
    class ParserAction(Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs not allowed")
            super(ParserAction, self).__init__(option_strings, dest, **kwargs)
            self.rootLogging = rootLogging
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, values)
            EnablePresetLogging(values, rootLogging=self.rootLogging)
            
    if rootLogging:
        longName = "--logging"
        help = "Enable logging. Default values are %s" % PRESET_LEVELS,
    else:
        longName = "--playground-logging"
        help = "Enable logging for the playground framework. Default values are %s" % PRESET_LEVELS,
        
    parser.add_argument(longName,
                        dest="playground_logging",
                        default=default,
                        help=help,
                        action=ParserAction)
    if default != None:
        EnablePresetLogging(default, rootLogging)
