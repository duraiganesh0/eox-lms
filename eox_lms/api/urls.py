""" urls.py """

from django.urls import include, re_path
app_name = 'eox_lms'  # pylint: disable=invalid-name

urlpatterns = [  # pylint: disable=invalid-name
    re_path(r'^v1/', include('eox_lms.api.v1.urls', namespace='eox-api')),
]
