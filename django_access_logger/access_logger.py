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

Utilities to build our AccessLog dict
"""
class AccessLogBuilder():
    """
    Builds log payload from Werkzeug request/response bodies
    Also contains a utility to flatten a JSON dict
    """
    def __init__(self, settings):
        self.conf = settings

    def build_log_dict(self, request, exceptions, response, duration,
                       log_bodies):
        """
        Creates a log dict from the request's metadata as well as the response
        and (possibly empty) list of exceptions triggered during the request
        processing
        """
        # Let's normalize our header names
        request_meta = {k.lower(): val for k, val in request.META.items()}
        request_headers = {}
        for k, val in request_meta.items():
            key = k
            if k.startswith('http_'):
                key = k[5:]
            elif k.startswith('content_'):
                key = k
            else:
                continue

            request_headers[key] = val

        response_headers = {name.lower(): ",".join(values[1:])
                            for (name, values)
                            in response._headers.items()}

        # And let's decode our bodies to UTF-8, if possible
        req_body = "not logged"
        req_size = int(request_headers["content_length"]) \
                if "content_length" in request_headers else 0

        resp_body = "not logged"
        if log_bodies:
            req_body = request_meta.get('aalm_request_body', None)
            if req_body is not None:
                try:
                    req_body = req_body.decode('utf-8')
                except UnicodeDecodeError:
                    req_body = "error decoding body to UTF-8"

            resp_body = response.content[:self.conf["MAX_BODY_SIZE"]]
            try:
                resp_body = resp_body.decode('utf-8')
            except UnicodeDecodeError:
                resp_body = "Error decoding body to UTF-8"

        # Let's "flatten" items from the aalm_exceptions list
        # (traceback.format_exception returns a list, not a string)
        errors = ["".join(item)
                  for item in request_meta.get('aalm_exceptions', [])]

        # When have everything, let's build and return our access log dict
        log_dict = {
            'duration': duration,
            'x_client_address': request_meta.get('remote_addr', 'unknown'),
            'errors': "\n".join(errors),
            'request': {
                'method': request.method,
                'http_version': request_meta.get('server_protocol', 'unknown'),
                'path': request.get_full_path(),
                'headers': request_headers,
                'content': {
                    'value': req_body,
                    'size': req_size,
                    'mime_type': request_meta.get('content_type','unknown')
                },
            },
            'response': {
                'status': response.status_code,
                'headers': response_headers,
                'content': {
                    'value': resp_body,
                    'size': len(response.content),
                    'mime_type': response._headers.get(
                        'content-type', (None, 'unknown')
                    )[-1]
                },
            },
        }

        if "aalm_extra_logs" in request_meta and \
                isinstance(request_meta["aalm_extra_logs"], dict):
            log_dict.update(request_meta["aalm_extra_logs"])

        return log_dict

    def flatten_dict(self, payload, path=None):
        """
        Flattens a given dict (performs a copy of the whole dict!)
        """
        res = {}
        for k, val in payload.items():
            subpath = ".".join([path, k]) if path is not None else k
            if isinstance(val, dict):
                res.update(self.flatten_dict(val, subpath))
            else:
                res[subpath] = val
        return res
