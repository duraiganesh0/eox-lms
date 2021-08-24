""" Support API urls.py """

from django.conf.urls import include, url

app_name = 'eox_lms'  # pylint: disable=invalid-name

urlpatterns = [  # pylint: disable=invalid-name
    url(r'^v1/', include('eox_lms.api.support.v1.urls', namespace='eox-support-api')),
]
