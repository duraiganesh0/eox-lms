#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Users public function definitions
"""

from importlib import import_module

from django.conf import settings


def get_group(name):
    """ Get the group by name """
    return group_backend().get_group(name)


def get_all_groups():
    """ Gets the all thee groups """
    return group_backend().get_all_groups()


def get_groups(user):
    """ Gets the groups for the user """
    return group_backend().get_groups(user)


def group_backend():
    """ Get the backend for the groups """
    return import_module(settings.EOX_CORE_GROUPS_BACKEND)
