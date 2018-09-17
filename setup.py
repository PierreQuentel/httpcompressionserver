from setuptools import setup

setup(
    name='httpcompressionserver',

    version='0.1',
    description='Add support of HTTP compression to standard library module http.server',


    # The project's main homepage.
    url='https://github.com/PierreQuentel/httpcompressionserver',

    # Author details
    author='Pierre Quentel',
    author_email='quentel.pierre@orange.fr',

    # Choose your license
    license='BSD',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',

        'Operating System :: OS Independent',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: BSD License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
    ],

    # What does your project relate to?
    keywords='Python HTTP server compression',

    py_modules=["httpcompressionserver"]

)