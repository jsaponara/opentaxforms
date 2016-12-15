from setuptools import setup
import io
import os
from opentaxforms.version import appversion

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README.md', 'CHANGES.md')

setup(
    name='opentaxforms',
    version=appversion,
    url='http://github.com/jsaponara/opentaxforms/',
    license="Affero GNU General Public License v3",
    author='John Saponara',
    tests_require=['pytest'],
    install_requires=['Pint>=0.7.2',
        'argparse>=1.2.1',
        'lxml>=3.6.4',
        'SQLAlchemy>=1.0.15',
        'pdfminer>=20140328',
        'Flask==0.11.1',
        'Flask-Restless==0.17.0',
        'Flask-SQLAlchemy==2.1',
        ],
    scripts = ['script/otf'],
    author_email='john@opentaxforms.org',
    description='Modernizes tax forms and provides an API for new tax form interfaces',
    long_description=long_description,
    packages=['opentaxforms'],
    package_dir={'opentaxforms':
                 'opentaxforms'},
    include_package_data=True,
    platforms='any',
    test_suite='test.test_opentaxforms',
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 3 - Alpha',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        ],
)
