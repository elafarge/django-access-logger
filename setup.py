from setuptools import setup

setup(
    name='django-access-logger',
    version='0.3.4',
    description='Access logging for Django, the right way',
    author="Étienne Lafarge",
    author_email="etienne.lafarge@gmail.com",
    url="https://github.com/elafarge/django-access-logger",
    # TODO: download URL
    license='Apache2',
    packages=['django_access_logger'],
    zip_safe=False,
    install_requires=[],
    include_package_data=True,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
        'Framework :: Django',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
        'Topic :: System :: Logging',
  ],
)
