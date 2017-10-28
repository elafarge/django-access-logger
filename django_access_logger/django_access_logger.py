# encoding: utf-8
"""
                               LICENSE

   Copyright 2017 Étienne Lafarge

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

                              -----------

A Django middleware that logs requests to the django.advanced_access_logs
logger, with configurable request/response body logging policies and the ability
to add custom adapters to alter your JSON payload before it is sent to the
django.advanced_access_logs logger.

You can really use that logger as you would with any other logger built atop the
official logging module from Python's standard library.

"""

# Python 2 compatibility :(
from __future__ import unicode_literals

# stl
import re
import sys
import time
import logging
import traceback

# 3p
from django.conf import settings

# Project
from .access_logger import AccessLogBuilder

# Necessary in order to maintain retro-compatibility with older versions of
# Django...
try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    class MiddlewareMixin(object):
        """
        Blank class for older versions of Django where MiddlewareMixin
        doesn't exist
        """
        def __init__(self, get_response):
            pass


# Methods for which we'll never ever try to log requests bodies.
NO_REQUEST_BODY_METHODS = [
    "get", "head", "delete", "options", "trace", "connect"
]

DEFAULT_CONFIG = {
    "ADAPTERS": [],
    "BODY_LOG_LEVEL": logging.WARNING,
    "DEBUG_REQUESTS": [],
    "MAX_BODY_SIZE": 5*1024,
}

class AccessLogsMiddleware(MiddlewareMixin):
    """
    A Django middleware that logs requests/responses as JSON, the clean and
    exloitable way
    """
    def __init__(self, get_response=None):
        """ Instantiates our Middleware """
        MiddlewareMixin.__init__(self, get_response)

        # Update the default config with user defined config
        self.conf = DEFAULT_CONFIG
        if hasattr(settings, "ACCESS_LOGS_CONFIG"):
            self.conf.update(settings.ACCESS_LOGS_CONFIG)

        # Instantiate our log building facility
        self.log_builder = AccessLogBuilder(self.conf)

        # And register our logger
        self.logger = logging.getLogger("django.advanced_access_logs")

        # Let's precompile our health check regexes
        for entry in self.conf["DEBUG_REQUESTS"]:
            for (k, val) in entry.items():
                entry[k] = re.compile(val)

    def process_request(self, request):
        """
        Called before the request hits the view (you decide when by putting
        the middleware in the right position. It stores request metadata so that
        we can retrieve them before forwarding the response to our client.
        """
        # Let's keep track of the original request data
        request.META["aalm_timestamp_started"] = time.time()
        request.META["aalm_original_request"] = request
        request.META["aalm_exceptions"] = []

        # If necessary let's log the body as well
        if request.method.lower() not in NO_REQUEST_BODY_METHODS and \
                self.conf["BODY_LOG_LEVEL"] is not None:
            request.META['aalm_request_body'] = \
                request.body[:self.conf["MAX_BODY_SIZE"]]

    def process_exception(self, request, exception):
        """
        Stores encountered exceptions in the request metadata
        """
        exc_type, exc_value, exc_traceback = sys.exc_info()
        request.META['aalm_exceptions'].append(traceback.format_exception(
            exc_type, exc_value, exc_traceback
        ))

    def process_response(self, request, response):
        """
        Called before the response is sent to the client, it computes the
        request duration, retrieves the original request metadata and sends all
        that to our logging module
        """
        duration = time.time() - request.META["aalm_timestamp_started"]

        # Determine wether or not bodies should be logged
        lvl = logging.INFO
        if response.status_code//100 == 5:
            lvl = logging.ERROR
        elif response.status_code//100 == 4:
            lvl = logging.WARN

        access_log = self.log_builder.build_log_dict(
            request.META["aalm_original_request"],
            request.META["aalm_exceptions"],
            response,
            duration,
            lvl >= self.conf["BODY_LOG_LEVEL"],
        )

        # Run user-defined log adapters
        for adapter in self.conf["ADAPTERS"]:
            adapter(request, access_log)

        # Flatten the log dict
        access_log = self.log_builder.flatten_dict(access_log)

        # Determine if the request should be logged under the DEBUG level
        if self.should_be_logged_as_debug(access_log):
            lvl = logging.DEBUG

        access_log["level"] = logging.getLevelName(lvl).lower()

        self.logger.log(lvl, "request processed", extra=access_log)

        return response

    def should_be_logged_as_debug(self, log):
        """ Returns true if the request is in the list of requests we want to
        log at the debug level """
        for entry in self.conf["DEBUG_REQUESTS"]:
            matches = True

            # Let's see if all regexes in this group do match
            for (k, reg) in entry.items():
                if k not in log or reg.match(log[k]) is None:
                    matches = False
                    break

            if matches:
                return True

        # No entry was matched
        return False
