Access logging for Django, the right way
========================================

Introduction
------------

A Django middleware that logs requests to the `django.advanced_access_logs`
logger, with configurable request/response body logging policies and the ability
to add custom adapters to alter your JSON payload before it is sent to the
`django.advanced_access_logs` logger.

You can really use that logger as you would with any other logger built atop the
official `logging` module from Python's standard library.

You can use this middleware to send exhaustive access logs as JSON to the log
aggregation of your choice, would it be [Fluentd](https://www.fluentd.org/)
(over http or by simply sending your logs to `stdout` and have fluentd parse
them from here), [Logstash](https://www.elastic.co/fr/products/logstash),
[logmatic/datadog](https://logmatic.io/), Splunk, Sumologic, etc.

Have fun collecting and analysing your logs !

Features
--------
* **Complete**: headers, bodies (if configured to do so), duration are all
  logged, once installed, you get 100% visibility on what happens (or happened)
  in your Django applications.
* **Configurable**: you can send specific request at the `DEBUG` level (for
  instance to remove health checks & other sources of noise from your logs), log
  bodies (or just log them in case an error occurs), obfuscate sensitive fields,
  add custom fields to your log entries... read below for details.
* **Pluggable**: The middleware simply collects request logs, you decide how you
  format them and where you send them using the `logging` module from the
  standard library.
* **Compatible with Python 2 & 3** (even though you probably should be using
  Python3 now, in particular because we use the `dict.items()` method - which is
  considered inefficiont in Python2). It should also support older versions of
  Django (tested on 1.9 -> 1.11, I'd be glad to gather feedback on how things go
  with older/newer versions of Django).
* **Lightweight**: the module only relies on standard library (+Django) and is
  about 300 lines of Python code. It's fast to install and easy to contribute
  to :)
* **Threadsafe**: simply because log emission is deferred to the standard
  `logging` library, which is threadsafe. Logs will never overlap on stdout and
  should therefore always remain parsable.

Installation
------------

#### 1. Enable the middleware
As any other Django middleware, install it first:
```shell
pip install django-access-logger           # or update your requirements.txt
```

And simply add it to your list of enabled middleware in your Django settings:
```python
MIDDLEWARE_CLASSES.insert(0, 'django_access_logger.AccessLogsMiddleware')
```

#### 2. Configure formatters & handlers
You then need to configure a formatter and handler to tell where these access
logs should go. If you need to familiarize yourself with how logging is done in
Django, [this](https://docs.djangoproject.com/en/1.11/topics/logging/) page may
help. Note that Django relies on the standard logging library, you might
therefore want to [check out this page](https://docs.python.org/3/library/logging.html)
as well.

Here's an example configuration using the `dictConfig` method
```python
# in your django project settings file
MIDDLEWARE_CLASSES.insert(0, 'django_access_logger.AccessLogsMiddleware')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'bare': {
            'format': '%(message)s',
        },
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'formatter': 'bare'
        },
    },
    'loggers': {
        'django.advanced_access_logs': {
            'level': 'INFO',
            'handlers': ['stdout'],
            'propagate': False,
        },
    },
}

```

##### Note
Depending on the position of your middleware in the list, some requests might
not be logged. In particular, if your middleware is triggered **after** an
authentication middleware, requests that don't pass the authentication
middleware will not be collected. It is therefore advised to put the middleware
**before** all other middlewares, hence using `insert(0, ...)` instead of
`append()`.

Advanced access logging configuration
-------------------------------------
The middleware's configuration belongs to your usual Django settings file(s), in
an `ACCESS_LOGGER_CONFIG` `dict` whose keys are described below.

### Logging levels
`4xx` requests are logged at the `WARNING` level, `5xx` at the `ERROR` level and
other requests are logged at the `INFO` level. This is not configurable for now
but such a feature could easily be added if required.

### Sending specific requests to DEBUG
You can configure the middleware to log predetermined requests at the `DEBUG`
level (for instance your health checks/liveness probes, etc.) and disable
`DEBUG` logging on prod to limit the noice induced by your health checks.
Moreover, you'll be able to re-enable them by simply lowering the
`django.advanced_access_logs` logger's level to `DEBUG`.

```python
# Note: even though we're
ACCESS_LOGS_CONFIG["DEBUG_REQUESTS"] = [
  {"request.path": "^/healthz$"},
  {"request.headers.user-agent", "Datadog", "request.path": "^/$"},
]
```

In the above example, all requests going to the `healthz` path will be logged
with a `DEBUG` level, as well as requests whose `User-Agent` header contains the
`Datadog Agent` string made against the `/` path.

##### Regexes and performance
Even though our regexes are precompiled when the middleware starts, Regexes in
Python are known to be slow. In case you're targeting high performance (but if
you're using Django you probably aren't anyways), it is better to keep the
`DEBUG_REQUESTS` list empty.

### Body logging policy
The config can be altered to log bodies depending on the logging level of
the request. If `BODY_LOG_LEVEL` is set to `None`, no bodies will ever be
logged.  By default, `BODY_LOG_LEVEL = logging.WARNING`.

Additionally, you can use the `MAX_BODY_SIZE` parameter to limit the size of the
bodies you are logging (strongly recommended). By default, `MAX_BODY_SIZE =
5*1024 # 5 KiB`.

```python
ACCESS_LOGS_CONFIG["BODY_LOG_LEVEL"] = logging.DEBUG # Log all bodies
ACCESS_LOGS_CONFIG["MAX_BODY_SIZE"] = 10*1024 # 10KiB
```

##### Note
`GET`, `HEAD`, `DELETE`, `OPTIONS`, `TRACE` and `CONNECT` requests should not
contain a body, therefore, we're bypassing the request body logging logic for
these request types: there will be no attempt to read the request body in such
cases, at least not in our middleware logic. (If you're not reading the request
body either, nor is any other middleware, then the corresponding views shouldn't
be vulnerable to [Slowloris](https://fr.wikipedia.org/wiki/Slowloris) attacks).

##### Limiting the middleware's RAM usage with `MAX_BODY_SIZE`
In case requests (or responses) contain **big** bodies (typically, file uploads
above a few KiBs), you have to keep in mind that these bodies will be stored in
RAM. AFAIK there's no clean way to control that in Django itself, however you
can at least control the number of bytes that will be logged (and therefore,
copied in RAM) with `MAX_BODY_SIZE`, at least, you won't load big bodies in RAM
twice...

### Altering your logs
You might want to remove some fields from your log payload, for that, you can
register an adapter that will be called after the log payload has been
processed, but before it is sent to the logger. We pass you the `log_dict`
object that contains log fields, you change it (without restrictions), that's
all.

#### Obfuscating sensitive fields (such as basic auth passwords)
The following example shows how to add a custom adapter that removes the
`authorization` header from the log payload after extracting the username from
it in a `username` field (if the Authorization header contained basic auth
credentials:

```python
def obsfuscate_auth(request, log_dict):
    auth = log_dict["requests"]["headers"]["authorization"] or None
    # No authorization header could be found ? Abort !
    if auth is None:
        return

    # Let's delete the Authorization header
    del log_dict["requests"]["headers"]["authorization"]

    # If it was a Basic auth header, let's log the username (not the password)
    if auth.startswith("Basic "):
        auth = auth.replace("Basic ", "")
        try:
            auth_creds = base64.b64decode(auth.decode("utf-8")).split(":", 1)
            log_dict["requests"]["headers"]["username"] = auth_creds[0]
        except UnicodeDecodeError:
            pass

ACCESS_LOGS_CONFIG.CONFIG["ADAPTERS"] = [obfuscate_auth]
```

IMPORTANT NOTE: depending on what you're logging and who has access to these
logs, it is your entire responsibility to anonymize/pseudonymize your logs would
they contain sensitive data. In the particular context of Basic Auth, it is
**essential** that you never logs your users' passwords!

### Sending your custom log lines

You can - obviously - send custom log lines to the `django.advanced_access_logs`
logger if you want to. However, if your message happens it the context of a
request, it is probably preferable to add a field to the access log itself
rather than emiting a log line that wouldn't carry request metadata.  We're
providing a helper tool for that: you simply need to create an `extra_logs` dict
in your `request.META` entry, we'll parse it and add it to the log for you
later. Be careful: your keys could overwrite existing fields which might be what
you want... or not. Choose you key names with care.

```python
# in your view
request.META["aalm_extra_logs"] = {"event": "long db call", "tag1": "parse_request"}
```

The `event` and `tag1` fields will be added at the root of your log payload.

### Disabling log flattening
Under the hood, your logs are stored and processed as a multilevel dict (the
`request` field contains a dict with a `headers` field containing a flat dict
with all the request headers. However, to be compatible with all formatters,
we're flattening your log payload before sending it to our logger:

```json
{
  "request": {
    "headers": {
      "accept": "xxx",
      "content-length": "yyy"
    }
  }
}
```

becomes

```json
{
  "request.headers.accept": "xxx",
  "request.headers.content-length": "yyy"
}
```

If that's not the behaviour you desire (because your sending logs to a database
that perfectly supports non-flat JSON documents, for instance) you can disable
that behaviour with `ACCESS_LOGS_CONFIG["FLATTEN"] = False`.

Authors
-------
* Étienne Lafarge <etienne.lafarge _at_ gmail.com>
