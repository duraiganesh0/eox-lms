""" urls.py """

from django.conf.urls import include, url


app_name = 'eox_lms'  # pylint: disable=invalid-name

urlpatterns = [  # pylint: disable=invalid-name
    url(r'^api/', include('eox_lms.api.urls', namespace='eox-api'))
]
