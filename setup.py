from setuptools import setup

setup(
    name='TCPoverICMP',
    version='1.0',
    packages=['TCPoverICMP'],
    url='https://github.com/raphick99/TCPoverICMP',
    license='',
    author='Raphael Ickovics',
    author_email='raphealickovics@gmail.com',
    description='ICMP tunnel',
    entry_points={
        'console_scripts': [
            'forwarder = TCPoverICMP.forwarder_main:start_asyncio_main',
            'proxy = TCPoverICMP.proxy_main:start_asyncio_main',
        ],
    },
    install_requires=[
        'protobuf',
    ],
)
