"""
Utilities to format our access logs in a standardized way
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
        request_headers = {re.sub('^HTTP_', '', header).lower(): value
                           for (header, value)
                           in request.META.items()
                           if header.startswith('HTTP_')}

        response_headers = {name: values[1:]
                            for (name, values)
                            in response._headers.items()}

        # And let's decode our bodies to UTF-8, if possible
        req_body = "not logged"
        req_size = request.content_length if request and request.content_length\
            else 0
        resp_body = "not logged"
        if log_bodies:
            original_req_body = request.META.get('original_request_body', None)
            if req_body is not None:
                try:
                    req_body = original_req_body.decode('utf-8')
                except UnicodeDecodeError:
                    req_body = "error decoding body to UTF-8"

            resp_body = response.content[:self.conf["MAX_BODY_SIZE"]]
            try:
                resp_body = resp_body.decode('utf-8')
            except UnicodeDecodeError:
                resp_body = "Error decoding body to UTF-8"

        return {
            'duration': duration,
            'request': {
                'method': request.method,
                'path': request.get_full_path(),
                'headers': request_headers,
                'content': {
                    'value': req_body,
                    'size': req_size,
                    'mime_type': request.META.get('CONTENT_TYPE',
                                                  'application/octet-stream')
                },
            },
            'response': {
                'status': response.status_code,
                'status_text': response.reason_phrase,
                'http_version': 'HTTP/1.1',
                'headers': response_headers,
                'content': {
                    'value': resp_body,
                    'size': len(response.content),
                    'mime_type': response._headers.get(
                        'content-type', (None, 'application/octet-stream'))[-1]
                },
                'redirect_url': response._headers.get(
                    'location', ('location', '')
                )[-1]
            },
        }

    def flatten_dict(self, payload, path=""):
        """
        Flattens a given dict (performs a copy of the whole dict!)
        """
        res = {}
        for k, val in payload.items():
            if isinstance(val, dict):
                res.update(self.flatten_dict, val, ".".join([path, k]))
            else:
                res[".".join([path, k])] = val
        return res
