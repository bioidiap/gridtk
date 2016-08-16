from . import setshell
from . import tools
from . import manager
from . import local
from . import sge
from . import easy
from . import tests


def get_config():
  """Returns a string containing the configuration information.
  """
  import bob.extension
  return bob.extension.get_config(__name__)


# gets sphinx autodoc done right - don't remove it
__all__ = [_ for _ in dir() if not _.startswith('_')]
