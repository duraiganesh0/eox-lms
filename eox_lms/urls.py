""" urls.py """

from django.urls import include, re_path


app_name = 'eox_lms'  # pylint: disable=invalid-name

urlpatterns = [  # pylint: disable=invalid-name
    re_path(r'^api/', include('eox_lms.api.urls', namespace='eox-api'))
]
