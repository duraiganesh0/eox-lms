"""
API v1 views.
"""

# pylint: disable=too-many-lines
from __future__ import absolute_import, unicode_literals

import logging

import edx_api_doc_tools as apidocs
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.utils import six
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from eox_lms.api.v1.permissions import EoxCoreAPIPermission
from eox_lms.api.v1.serializers import (
    EdxappCourseEnrollmentQuerySerializer,
    EdxappCourseEnrollmentSerializer,
    # EdxappCoursePreEnrollmentSerializer,
    # EdxappGradeSerializer,
    EdxappUserQuerySerializer,
    EdxappUserReadOnlySerializer,
    EdxappUserSerializer,
    WrittableEdxappUserSerializer,
)
from eox_lms.edxapp_wrapper.bearer_authentication import BearerAuthentication
# from eox_lms.edxapp_wrapper.coursekey import get_valid_course_key
# from eox_lms.edxapp_wrapper.courseware import get_courseware_courses
from eox_lms.edxapp_wrapper.enrollments import create_enrollment, delete_enrollment, get_enrollment, update_enrollment, get_user_enrollments_for_course, get_user_enrollment_attributes
# from eox_lms.edxapp_wrapper.grades import get_course_grade_factory
# from eox_lms.edxapp_wrapper.pre_enrollments import (
#     create_pre_enrollment,
#     delete_pre_enrollment,
#     get_pre_enrollment,
#     update_pre_enrollment,
# )
from eox_lms.edxapp_wrapper.users import create_edxapp_user, get_edxapp_user, get_edxapp_users, get_user_read_only_serializer
from eox_lms.edxapp_wrapper.groups import get_group, get_groups, get_all_groups


try:
    from eox_audit_model.decorators import audit_drf_api
except ImportError:
    def audit_drf_api(*args, **kwargs):
        """Identity decorator"""
        return lambda x: x

LOG = logging.getLogger(__name__)


class UserQueryMixin:
    """
    Provides tools to create user queries
    """

    def __init__(self, *args, **kwargs):
        """
        Defines instance attributes
        """
        super(UserQueryMixin, self).__init__(*args, **kwargs)
        self.query_params = None
        self.site = None

    def initial(self, request, *args, **kwargs):
        """
        Loads the site into the object for every kind of request.
        """
        super(UserQueryMixin, self).initial(request, *args, **kwargs)

        if hasattr(request, "site"):
            self.site = request.site

    def get_query_params(self, request):
        """
        Utility to read the query params in a forgiving way
        As a side effect it loads self.query_params also in a forgiving way
        """
        query_params = request.query_params
        if not query_params and request.data:
            query_params = request.data

        self.query_params = query_params

        return query_params

    def get_user_query(self, request, query_params=None):
        """
        Utility to prepare the user query
        """
        if not query_params:
            query_params = self.get_query_params(request)

        username = query_params.get("username", None)
        email = query_params.get("email", None)

        # if not email and not username:
        #    raise ValidationError(detail="Email or username needed")

        user_query = {}
        if hasattr(self, "site") and self.site:
            user_query["site"] = self.site
        if username:
            user_query["username"] = username
        elif email:
            user_query["email"] = email

        return user_query


    def serialize(self, user, request):
        """ Serialize the user data addming the groups """
        admin_fields = getattr(settings, "ACCOUNT_VISIBILITY_CONFIGURATION", {}).get(
            "admin_fields", {}
        )
        serialized_user = EdxappUserReadOnlySerializer(
            user, custom_fields=admin_fields, context={"request": request}
        )
        return self.write_groups(user, serialized_user.data)


    def write_groups(self, user, json):
        """ Add the group data into the user response """
        user_json = {}
        for next in json:
            user_json[next] = json[next]

        user_json[self.groups_attr()] = []
        for next in get_groups(user):
            user_json[self.groups_attr()].append(next.name)

        return user_json


    def manage_groups(self, user, add, remove):
        """ Manage the groups for the user """
        for next in add:
            group = get_group(next)
            user.groups.add(group)

        for next in remove:
            group = get_group(next)
            user.groups.remove(group)

    def groups(self, json):
        """ Get the groups from the json """
        return json[self.groups_attr()] if json[self.groups_attr()] else []

    def groups_add(self, json):
        """ Get the groups to be added """
        return self.groups_(json, self.groups_add_attr())

    def groups_remove(self, json):
        """ Get the groups to be removed """
        return self.groups_(json, self.groups_remove_attr())

    def groups_(self, json, type):
        """ Get the groups for the specified type """
        groups = self.groups(json)
        return groups[type] if groups[type] else {}

    def groups_attr(self):
        return "groups"

    def groups_add_attr(self):
        return "add"

    def groups_remove_attr(self):
        return "remove"


class EdxappUser(UserQueryMixin, APIView):
    """
    Handles the creation of a User on edxapp

    **Example Requests**

        POST /eox-lms/api/v1/user/

        Request data: {
            "username": "johndoe",
            "email": "johndoe@example.com",
            "fullname": "John Doe",
            "password": "p@ssword",
        }

    The extra registration fields configured for the microsite, should be sent along with the rest of the parameters.
    These extra fields would be required depending on the settings.
    For example, if we have the microsite settings:

        "EDNX_CUSTOM_REGISTRATION_FIELDS": [
            {
                "label": "Personal ID",
                "name": "personal_id",
                "type": "text"
            },
        ],

        "REGISTRATION_EXTRA_FIELDS": {
            "gender": "required",
            "country": "hidden",
            "personal_id": "required",
        },

        "extended_profile_fields": [
            "personal_id",
        ],

    Then a request to create a user should look like this:

        {
            "username": "johndoe",
            "email": "johndoe@example.com",
            "fullname": "John Doe",
            "password": "p@ssword",
            "gender": "m",
            "country": "GR",
            "personal_id": "12345",
        }

    """

    authentication_classes = (BearerAuthentication, SessionAuthentication)
    permission_classes = (EoxCoreAPIPermission,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)

    @apidocs.schema(
        body=EdxappUserQuerySerializer,
        responses={
            200: EdxappUserSerializer,
            400: "Bad request, a required field is missing or has been entered with the wrong format.",
            401: "Unauthorized user to make the request.",
        },
    )
    @audit_drf_api(
        action="Create edxapp user",
        data_filter=[
            "email",
            "username",
            "fullname",
        ],
        hidden_fields=["password"],
        save_all_parameters=True,
        method_name='eox_core_api_method',
    )
    def post(self, request, *args, **kwargs):
        """
        Handles the creation of a User on edxapp

        **Example Requests**

            POST /eox-lms/api/v1/user/

            Request data: {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "fullname": "John Doe",
                "password": "p@ssword",
            }

        **Parameters**

        - `username` (**required**, string, _body_):
            The username to be assigned to the new user.

        - `email` (**required**, string, _body_):
            The email to be assigned to the new user.

        - `password` (**required**, string, _body_):
            The password of the new user. If `skip_password` is True, this field will be omitted.

        - `fullname` (**required**, string, _body_):
            The full name to be assigned.

        - `activate_user` (**optional**, boolean, default=False, _body_):
            Flag indicating whether the user is active.

        - `skip_password` (**optional**, boolean, default=False, _body_):
            Flag indicating whether the password should be omitted.

        If you have extra registration fields configured in your settings or extended_profile fields, you can send them with the rest of the parameters.
        These extra fields would be required depending on the site settings.
        For example:

            {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "fullname": "John Doe",
                "password": "p@ssword",
                "gender": "m",
                "country": "GR",
            }


        **Returns**

        - 200: Success, user created.
        - 400: Bad request, a required field is missing or has been entered with the wrong format, or the chosen email/username already belongs to a user.
        - 401: Unauthorized user to make the request.
        """
        serializer = EdxappUserQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data["site"] = get_current_site(request)
        user, msg = create_edxapp_user(**data)

        self.groups(request.data) and self.manage_groups(user, self.groups(request.data), [])

        serialized_user = EdxappUserSerializer(user)
        response_data = serialized_user.data
        response_data = self.write_groups(user, response_data)
        if msg:
            response_data["messages"] = msg
        return Response(response_data)

    @apidocs.schema(
        parameters=[
            apidocs.query_parameter(
                name="username",
                param_type=str,
                description="**required**, The username used to identify the user. Use either username or email.",
            ),
            apidocs.query_parameter(
                name="email",
                param_type=str,
                description="**required**, The email used to identify the user. Use either username or email.",
            ),
        ],
        responses={
            200: get_user_read_only_serializer(),
            400: "Bad request, missing email or username",
            401: "Unauthorized user to make the request.",
            404: "User not found",
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieves information about an edxapp user,
        given an email or a username.

        The username prevails over the email when both are provided to get the user.

        **Example Requests**

            GET /eox-lms/api/v1/user/?username=johndoe

            Query parameters: {
              "username": "johndoe",
            }

        **Response details**

        - `username (str)`: Username of the edxapp user
        - `is_active (str)`: Indicates if the user is active on the platform
        - `email (str)`: Email of the user
        - `gender (str)`: Gender of the user
        - `date_joined (str)`: Date for when the user was registered in the platform
        - `name (str)`: Fullname of the user
        - `country (str)`: Country of the user
        - `level_of_education (str)`: Level of education of the user
        - `year_of_birth (int)`: Year of birth of the user
        - `bio (str)`: Bio of the user
        - `goals (str)`: Goals of the user
        - `extended_profile (list)`: List of dictionaries that contains the user-profile meta fields
            - `field_name (str)`: Name of the extended profile field
            - `field_value (str)`: Value of the extended profile field
        - `mailing_address (str)`
        - `social_links (List)`: List that contains the social links of the user, if any.
        - `account_privacy (str)`: Indicates the account privacy type
        - `state (str)`: State (only for US)
        - `secondary_email (str)`: Secondary email of the user
        - `profile_image (dictionary)`:
            - `has_image (Bool)`: Indicates if user has profile image
            - `image_url_medium (str)`: Url of the profile image in medium size
            - `image_url_small (str)`: Url of the profile image in small size
            - `image_url_full (str)`: Url of the profile image in full size,
            - `image_url_large (str)`: Url of the profile image in large size
        - `secondary_email_enabled (Bool)`: Indicates if the secondary email is enable
        - `phone_number (str)`: Phone number of the user
        - `requires_parental_consent (Bool)`: Indicates whether parental consent is required for the user

        **Returns**

        - 200: Success, user found.
        - 400: Bad request, missing either email or username
        - 401: Unauthorized user to make the request.
        - 404: User not found
        """

        query = self.get_user_query(request)

        data = self.get_single_user(query, request) if self.single_request(query) else self.get_all_users(request)

        return Response(data)

    def single_request(self, query):
        """ Return true if the query is a single user request """
        return "username" in query or "email" in query

    def get_single_user(self, query, request):
        """ Get a single user """
        user = get_edxapp_user(**query)
        data = self.serialize(user, request)
        return data

    def get_all_users(self, request):
        """ Get all the users for edx """
        users = get_edxapp_users()
        data = []
        for next in users:
            data.append(self.serialize(next, request))
        return data


class EdxappUserUpdater(UserQueryMixin, APIView):
    """
    Partially updates a user from edxapp.

    Not all the fields can be updated, just the ones thought as `safe`. By default, this fields are the ones defined in the
    EOX_CORE_USER_UPDATE_SAFE_FIELDS

    **Example Requests**

        PATCH /eox-lms/api/v1/update-user/

        Request data: {
            "email": "johndoe@example.com",
            "fullname": "John Doe R",
            "password": "new-p@ssword",
        }

    The extra registration fields configured for the microsite, should be sent along with the rest of the parameters.
    These extra fields would be required (their value cannot be changed to null) depending on the settings.

    For example, if we have the microsite settings:

        "EDNX_CUSTOM_REGISTRATION_FIELDS": [
            {
                "label": "Personal ID",
                "name": "personal_id",
                "type": "text"
            },
        ],

        "REGISTRATION_EXTRA_FIELDS": {
            "gender": "required",
            "country": "hidden",
            "personal_id": "required",
        },

        "extended_profile_fields": [
            "personal_id",
        ],

    Then a request to create a user should look like this:

        {
            "email": "johndoe@example.com",
            "fullname": "John Doe R",
            "password": "new-p@ssword",
            "country": "CO",
            "personal_id": "00099",
        }
    """

    authentication_classes = (BearerAuthentication, SessionAuthentication)
    permission_classes = (EoxCoreAPIPermission,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)

    @apidocs.schema(
        body=WrittableEdxappUserSerializer,
        responses={
            200: get_user_read_only_serializer(),
            400: "Bad request, a required field is now null or has been entered with the wrong format.",
            401: "Unauthorized user to make the request.",
            404: "User not found.",
        },
    )
    @audit_drf_api(
        action='Partially update a user from edxapp',
        data_filter=[
            'email',
            'is_active',
        ],
        hidden_fields=['password'],
        save_all_parameters=True,
        method_name='eox_core_api_method',
    )
    def patch(self, request, *args, **kwargs):
        """
        Partially updates a user from edxapp.

        **Example Requests**

            PATCH /eox-lms/api/v1/update-user/

            Request data: {
                "email": "johndoe@example.com",
                "fullname": "John Doe R",
                "password": "new-p@ssword",
            }


        **Parameters**

        - `email` (**required**, string, _body_):
            The email used to identify the user. Use either username or email.

        - `username` (**required**, string, _body_):
            The username used to identify the user. Use either username or email.

        - `password` (**optional**, string, _body_):
            The new password of the user.

        - `fullname` (**optional**, string, _body_):
            The full name to be assigned.

        - `is_active` (**optional**, boolean, _body_):
            Flag indicating if the user is active on the platform.

        - Not all the fields can be updated, just the ones thought as 'safe', such as: "is_active", "password", "fullname"

        - By default, these are the 'safe' extra registration fields: "mailing_address", "year_of_birth", "gender", "level_of_education",
        "city", "country", "goals", "bio" and "phone_number".

        If you have extra registration fields configured in your settings or extended_profile fields, and you want to update them, you can send them along with the rest of the parameters.
        For example:

            {
                "email": "johndoe@example.com",
                "fullname": "John Doe R",
                "password": "new-p@ssword",
                "gender": "f",
                "country": "US",
            }

        **Response details**

        - `username (str)`: Username of the edxapp user
        - `is_active (str)`: Indicates if the user is active on the platform
        - `email (str)`: Email of the user
        - `gender (str)`: Gender of the user
        - `date_joined (str)`: Date for when the user was registered in the platform
        - `name (str)`: Fullname of the user
        - `country (str)`: Country of the user
        - `level_of_education (str)`: Level of education of the user
        - `year_of_birth (int)`: Year of birth of the user
        - `bio (str)`: Bio of the user
        - `goals (str)`: Goals of the user
        - `extended_profile (list)`: List of dictionaries that contains the user-profile meta fields
            - `field_name (str)`: Name of the extended profile field
            - `field_value (str)`: Value of the extended profile field
        - `mailing_address (str)`
        - `social_links (List)`: List that contains the social links of the user, if any.
        - `account_privacy (str)`: Indicates the account privacy type
        - `state (str)`: State (only for US)
        - `secondary_email (str)`: Secondary email of the user
        - `profile_image (dictionary)`:
            - `has_image (Bool)`: Indicates if user has profile image
            - `image_url_medium (str)`: Url of the profile image in medium size
            - `image_url_small (str)`: Url of the profile image in small size
            - `image_url_full (str)`: Url of the profile image in full size,
            - `image_url_large (str)`: Url of the profile image in large size
        - `secondary_email_enabled (Bool)`: Indicates if the secondary email is enable
        - `phone_number (str)`: Phone number of the user
        - `requires_parental_consent (Bool)`: Indicates whether parental consent is required for the user

        **Returns**

        - 200: Success, user updated.
        - 400: Bad request, a required field is now null or has been entered with the wrong format.
        - 401: Unauthorized user to make the request.
        - 404: User not found
        """
        # Pop identification
        data = request.data.copy()
        query_params = {
            "email": data.pop("email", None),
            "username": data.pop("username", None),
        }
        query = self.get_user_query(request, query_params=query_params)
        user = get_edxapp_user(**query)

        serializer = WrittableEdxappUserSerializer(user, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.manage_groups(user, self.groups_add(data), self.groups_remove(data))

        data = self.serialize(user, request)
        return Response(data)


class EdxappEnrollment(UserQueryMixin, APIView):
    """
    Handles API requests to create users
    """

    authentication_classes = (BearerAuthentication, SessionAuthentication)
    permission_classes = (EoxCoreAPIPermission,)
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer)

    @apidocs.schema(
        body=EdxappCourseEnrollmentQuerySerializer,
        responses={
            200: EdxappCourseEnrollmentQuerySerializer,
            202: "User doesn't belong to site.",
            400: "Bad request, invalid course_id or missing either email or username.",
        },
    )
    @audit_drf_api(
        action='Create single or bulk enrollments',
        data_filter=[
            'email',
            'username',
            'course_id',
            'mode',
            'is_active',
            'enrollment_attributes',
        ],
        method_name='eox_core_api_method',
    )
    def post(self, request, *args, **kwargs):
        """
        Handle creation of single or bulk enrollments

        **Example Requests**

            POST /eox-lms/api/v1/enrollment/

            Request data: {
              "username": "johndoe",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
              "mode": "audit",
              "force": "False",
              "is_active": "False",
              "enrollment_attributes": [
                {
                  "namespace": "credit",
                  "name": "provider_id",
                  "value": "institution_name"
                }
              ]
            }

        **Parameters**

        - `username` (**required**, string, _body_):
            The username used to identify the user you want to enroll.  Use either username or email.

        - `email` (**required**, string, _body_):
            The email used to identify the user you to enroll.  Use either username or email.

        - `course_id` (**required**, string, _body_):
            The id of the course in which you want to enroll the user.

        - `mode` (**required**, string, _body_):
            The course mode for the enrollment.  Must be available for the course.

        - `is_active` (boolean, _body_):
            Flag indicating whether the enrollment is active.

        - `force` (boolean, _body_):
            Flag indicating whether the platform business rules for enrollment must be skipped. When it is true, the enrollment
            is created without looking at the enrollment dates, if the course is full, if the enrollment mode is part of the modes
            allowed by that course and other course settings.

        - `enrollment_attributes` (list, _body_):
            List of enrollment attributes. An enrollment attribute can be used to add extra parameters for a specific course mode.
            It must be a dictionary containing the following:
            - namespace: namespace of the attribute
            - name: name of the attribute
            - value: value of the attribute

        In case the case of bulk enrollments, you must provide a list of dictionaries containing
        the parameters specified above; the same restrictions apply.
        For example:

            [{
              "username": "johndoe",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
              "mode": "audit",
              "is_active": "False",
              "force": "False",
              "enrollment_attributes": [
                {
                  "namespace": "credit",
                  "name": "provider_id",
                  "value": "institution_name"
                }
              ]
             },
             {
              "email": "janedoe@example.com",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
              "mode": "audit",
              "is_active": "True",
              "force": "False",
              "enrollment_attributes": []
             },
            ]

        **Returns**

        - 200: Success, enrollment created.
        - 202: User doesn't belong to site.
        - 400: Bad request, invalid course_id or missing either email or username.
        """
        data = request.data
        return EdxappEnrollment.prepare_multiresponse(
            data, self.single_enrollment_create
        )

    @apidocs.schema(
        body=EdxappCourseEnrollmentQuerySerializer,
        responses={
            200: EdxappCourseEnrollmentQuerySerializer,
            202: "User or enrollment doesn't belong to site.",
            400: "Bad request, invalid course_id or missing either email or username.",
        },
    )
    @audit_drf_api(
        action='Update enrollments on edxapp',
        data_filter=[
            'email',
            'username',
            'course_id',
            'mode',
            'is_active',
            'enrollment_attributes',
        ],
        method_name='eox_core_api_method',
    )
    def put(self, request, *args, **kwargs):
        """
        Update enrollments on edxapp

        **Example Requests**

            PUT /eox-lms/api/v1/enrollment/

            Request data: {
              "username": "johndoe",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
              "mode": "audit",
              "is_active": "False",
              "enrollment_attributes": [
                {
                  "namespace": "credit",
                  "name": "provider_id",
                  "value": "institution_name"
                }
              ]
            }

        **Parameters**

        - `username` (**required**, string, _body_):
            The username used to identify a user enrolled on the course. Use either username or email.

        - `email` (**required**, string, _body_):
            The email used to identify a user enrolled on the course. Use either username or email.

        - `course_id` (**required**, string, _body_):
            The course id for the enrollment you want to update.

        - `mode` (**required**, string, _body_):
            The course mode for the enrollment. Must be available for the course.

        - `is_active` (boolean, _body_):
            Flag indicating whether the enrollment is active.

        - `enrollment_attributes` (list, _body_):
            An enrollment attribute can be used to add extra parameters for a specific course mode.
            It must be a dictionary containing the following:
            - namespace: namespace of the attribute
            - name: name of the attribute
            - value: value of the attribute

        **Returns**

        - 200: Success, enrollment updated.
        - 202: User or enrollment doesn't belong to site.
        - 400: Bad request, invalid course_id or missing either email or username.
        """
        data = request.data
        return EdxappEnrollment.prepare_multiresponse(
            data, self.single_enrollment_update
        )

    @apidocs.schema(
        parameters=[
            apidocs.query_parameter(
                name="username",
                param_type=str,
                description="**required**, The username used to identify a user enrolled on the course. Use either username or email.",
            ),
            apidocs.query_parameter(
                name="email",
                param_type=str,
                description="**required**, The email used to identify a user enrolled on the course. Use either username or email.",
            ),
            apidocs.query_parameter(
                name="course_id",
                param_type=str,
                description="**required**, The course id for the enrollment you want to check.",
            ),
        ],
        responses={
            200: EdxappCourseEnrollmentSerializer,
            400: "Bad request, missing course_id or either email or username",
            404: "User or course not found",
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieves enrollment information given a user and a course_id

        **Example Requests**

            GET /eox-lms/api/v1/enrollment/?username=johndoe&
            course_id=course-v1:edX+DemoX+Demo_Course

            Request data: {
              "username": "johndoe",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
            }

        **Returns**

        - 200: Success, enrollment found.
        - 400: Bad request, missing course_id or either email or username
        - 404: User or course not found
        """
        user_query = None
        user = None
        flag_get_all = True

        self.query_params = self.get_query_params(request)
        if self.query_params.get("username", None) is not None:
            user_query = self.get_user_query(request)
            user = get_edxapp_user(**user_query)
            flag_get_all = False

        course_id = self.query_params.get("course_id", None)

        if not course_id:
            raise ValidationError(detail="You have to provide a course_id")

        if flag_get_all == False:
            enrollment_query = {
                "username": user.username,
                "course_id": course_id,
            }
            enrollment, errors = get_enrollment(**enrollment_query)

            if errors:
                raise NotFound(detail=errors)
            response = EdxappCourseEnrollmentSerializer(enrollment).data
            return Response(response)
        else:
            enrollment_query = {
                "course_id": course_id,
            }
            enrollment_set, errors = get_user_enrollments_for_course(**enrollment_query)
            if errors:
                raise NotFound(detail=errors)
            
        
            enrollments_serialized = []

            for enrollment in enrollment_set.iterator():
                enrollment_model_serialized = EdxappCourseEnrollmentSerializer(enrollment).data
                enrollment_model_serialized['enrollment_attributes'] = get_user_enrollment_attributes(enrollment.username, course_id.replace(' ', '+'))
                enrollment_model_serialized['course_id'] = course_id.replace(' ','+')
                enrollments_serialized.append(enrollment_model_serialized)


            response = EdxappCourseEnrollmentSerializer(enrollments_serialized , many=True).data
            return Response(response)


    @apidocs.schema(
        parameters=[
            apidocs.query_parameter(
                name="username",
                param_type=str,
                description="**required**, The username used to identify a user enrolled on the course. Use either username or email.",
            ),
            apidocs.query_parameter(
                name="email",
                param_type=str,
                description="**required**, The email used to identify a user enrolled on the course. Use either username or email.",
            ),
            apidocs.query_parameter(
                name="course_id",
                param_type=str,
                description="**required**, The course id for the enrollment you want to check.",
            ),
        ],
        responses={
            204: "Empty response",
            400: "Bad request, missing course_id or either email or username",
            404: "User or course not found",
        },
    )
    @audit_drf_api(action='Delete enrollment on edxapp.', method_name='eox_core_api_method')
    def delete(self, request, *args, **kwargs):
        """
        Delete enrollment on edxapp

        **Example Requests**

            DELETE /eox-lms/api/v1/enrollment/

            Request data: {
              "username": "johndoe",
              "course_id": "course-v1:edX+DemoX+Demo_Course",
            }
        """
        user_query = self.get_user_query(request)
        user = get_edxapp_user(**user_query)

        course_id = self.query_params.get("course_id", None)

        if not course_id:
            raise ValidationError(detail="You have to provide a course_id")

        delete_enrollment(user=user, course_id=course_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def single_enrollment_create(self, *args, **kwargs):
        """
        Handle one create at the time
        """
        user_query = self.get_user_query(None, query_params=kwargs)
        user = get_edxapp_user(**user_query)

        enrollments, msgs = create_enrollment(user, **kwargs)
        # This logic block is needed to convert a single bundle_id enrollment in a list
        # of course_id enrollments which are appended to the response individually
        if not isinstance(enrollments, list):
            enrollments = [enrollments]
            msgs = [msgs]
        response_data = []
        for enrollment, msg in zip(enrollments, msgs):
            data = EdxappCourseEnrollmentSerializer(enrollment).data
            if msg:
                data["messages"] = msg
            response_data.append(data)

        return response_data

    def single_enrollment_update(self, *args, **kwargs):
        """
        Handle one update at the time
        """
        user_query = self.get_user_query(None, query_params=kwargs)
        user = get_edxapp_user(**user_query)

        course_id = kwargs.pop("course_id", None)
        if not course_id:
            raise ValidationError(detail="You have to provide a course_id for updates")
        mode = kwargs.pop("mode", None)

        return update_enrollment(user, course_id, mode, **kwargs)

    @staticmethod
    def prepare_multiresponse(request_data, action_method):
        """
        Prepare a multiple part response according to the request_data and the action_method provided
        Args:
            request_data: Data dictionary containing the query or queries to be processed
            action_method: Function to be applied to the queries (create, update)

        Returns: List of responses
        """
        multiple_responses = []
        errors_in_bulk_response = False
        many = isinstance(request_data, list)
        serializer = EdxappCourseEnrollmentQuerySerializer(data=request_data, many=many)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not isinstance(data, list):
            data = [data]

        for enrollment_query in data:

            try:
                result = action_method(**enrollment_query)
                # The result can be a list if the enrollment was in a bundle
                if isinstance(result, list):
                    multiple_responses += result
                else:
                    multiple_responses.append(result)
            except APIException as error:
                errors_in_bulk_response = True
                enrollment_query["error"] = {
                    "detail": error.detail,
                }
                multiple_responses.append(enrollment_query)

        if many or "bundle_id" in request_data:
            response = multiple_responses
        else:
            response = multiple_responses[0]

        response_status = status.HTTP_200_OK
        if errors_in_bulk_response:
            response_status = status.HTTP_202_ACCEPTED
        return Response(response, status=response_status)

    def handle_exception(self, exc):
        """
        Handle exception: log it
        """
        if isinstance(exc, APIException):
            LOG.error("API Error: %s", repr(exc.detail))

        return super(EdxappEnrollment, self).handle_exception(exc)
