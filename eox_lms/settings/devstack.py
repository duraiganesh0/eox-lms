"""
Settings for eox_lms project meant to be called on the edx-platform/*/envs/devstack.py module
"""
from .production import *  # pylint: disable=wildcard-import, unused-wildcard-import


def plugin_settings(settings):  # pylint: disable=function-redefined
    """
    Set of plugin settings used by the Open Edx platform.
    More info: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """
    # settings.EOX_CORE_STATICFILES_STORAGE = "eox_lms.storage.DevelopmentStorage"
    # if settings.EOX_CORE_ENABLE_STATICFILES_STORAGE:
    #     settings.STATICFILES_STORAGE = settings.EOX_CORE_STATICFILES_STORAGE
