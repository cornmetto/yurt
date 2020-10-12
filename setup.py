from setuptools import setup, find_packages

setup(
    name='yurt',
    version="0.1.0",
    py_modules=['yurt'],
    packages=find_packages(),
    install_requires=[
        'click',
        'fabric',
        'paramiko',
        'requests',
        'tabulate',
    ],
    entry_points='''
        [console_scripts]
        yurt=yurt.cli:main
    ''',
)
