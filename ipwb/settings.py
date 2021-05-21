"""Settings and configuration parameters of ipwb."""

import os
from logging import config as logging_config
from ipwb import util

# Running in debug mode or not?
DEBUG = os.environ.get('DEBUG', False)

IPFSAPI_MUTLIADDRESS = '/dns/localhost/tcp/5001/http'
# or '/dns/{host}/tcp/{port}/http'
# or '/ip4/{ipaddress}/tcp/{port}/http'
# or '/ip6/{ipaddress}/tcp/{port}/http

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False
        },
    }
}


logging_config.dictConfig(LOGGING)


class App:
    __conf = {
        "ipfsapi": IPFSAPI_MUTLIADDRESS
    }
    __setters = ["ipfsapi"]

    @staticmethod
    def config(name):
        return App.__conf[name]

    @staticmethod
    def set(name, value):
        if name in App.__setters:
            App.__conf[name] = value
        else:
            raise NameError("Name not accepted in set() method")
