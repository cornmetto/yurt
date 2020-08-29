from setuptools import setup
import config

setup(
    name='yurt',
    version="0.0.1",
    py_modules=['yurt'],
    install_requires=[
        'click',
    ],
    entry_points='''
        [console_scripts]
        yurt=cli:yurt
    ''',
)
