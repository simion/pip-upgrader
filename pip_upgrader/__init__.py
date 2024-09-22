from importlib.metadata import version 

try:
    __version__ = version('pip_upgrader')
except Exception:  # pragma: nocover
    __version__ = 'unknown'
 
