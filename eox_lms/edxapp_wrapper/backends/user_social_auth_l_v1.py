#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backend for the create_edxapp_user_social_auth that works under the open-release/lilac.master tag
"""
import logging

from social_django.models import UserSocialAuth

LOG = logging.getLogger(__name__)

def get_user_social_auths(**kwargs):
    """
    Return the all the user social auths
    """
    return UserSocialAuth.objects.filter(**kwargs)

def add_user_social_auth(**kwargs):
    """
    Create the user social auth
    """
    return UserSocialAuth.objects.create(**kwargs)
