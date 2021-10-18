#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backend for the create_edxapp_user that works under the open-release/lilac.master tag
"""
import logging

from django.contrib.auth.models import Group

LOG = logging.getLogger(__name__)


def get_group(name):
    """
    Return the group for the specified name
    """
    return Group.objects.get(name = name)

def get_all_groups():
    """
    Return the all the groups
    """
    return Group.objects.all()

def get_groups(user):
    """
    Return the groups for the user
    """
    return user.groups.all()
