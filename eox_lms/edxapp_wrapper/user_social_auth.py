#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Users public function definitions
"""

from importlib import import_module

from django.conf import settings


def get_user_social_auths(**kwargs):
    """ Gets the all the user social auths """
    return user_social_auth_backend().get_user_social_auths(**kwargs)

def add_user_social_auth(**kwargs):
    """ add the user social auth """
    return user_social_auth_backend().add_user_social_auth(**kwargs)


def user_social_auth_backend():
    """ Get the backend for the user social auths """
    return import_module(settings.EOX_CORE_USER_SOCIAL_AUTHS_BACKEND)
