""" urls.py """

from django.conf.urls import include, url

# from eox_lms import views
# from eox_lms.api_schema import docs_ui_view

app_name = 'eox_lms'  # pylint: disable=invalid-name

urlpatterns = [  # pylint: disable=invalid-name
    # url(r'^eox-info$', views.info_view),
    url(r'^api/', include('eox_lms.api.urls', namespace='eox-api')),
    # url(r'^data-api/', include('eox_lms.api.data.v1.urls', namespace='eox-data-api')),
    # url(r'^management/', include('eox_lms.cms.urls', namespace='eox-course-management')),
    # url(r'^api-docs/$', docs_ui_view, name='apidocs-ui'),
    # url(r'^tasks-api/', include('eox_lms.api.task_dispatcher.v1.urls', namespace='eox-task-api')),
    # url(r'^support-api/', include('eox_lms.api.support.urls', namespace='eox-support-api')),
]
