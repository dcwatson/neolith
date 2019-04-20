from setuptools import find_packages, setup

import neolith

import os


BASE_DIR = os.path.dirname(__file__)


def get_description():
    with open(os.path.join(BASE_DIR, 'README.md')) as readme:
        return readme.read().strip()


def get_requirements():
    with open(os.path.join(BASE_DIR, 'requirements.txt')) as reqs:
        def valid_req(s):
            return s and not s.startswith('#')
        return list(filter(valid_req, map(str.strip, reqs.read().splitlines())))


setup(
    name='neolith',
    version=neolith.version,
    description='Reference client/server for the neolith protocol.',
    long_description=get_description(),
    long_description_content_type='text/markdown',
    author='Dan Watson',
    author_email='dcwatson@gmail.com',
    url='https://github.com/dcwatson/neolith',
    license='MIT',
    packages=find_packages(),
    install_requires=get_requirements(),
    setup_requires=[
        'pytest-runner',
    ],
    tests_require=[
        'pytest',
    ],
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
    ],
)
