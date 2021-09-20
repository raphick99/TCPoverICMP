from setuptools import setup

setup(
    name='TCPoverICMP',
    version='1.0',
    packages=['tcp', 'core', 'icmp', 'proto', 'proxy', 'forwarder'],
    url='https://github.com/raphick99/TCPoverICMP',
    license='',
    author='Raphael Ickovics',
    author_email='raphealickovics@gmail.com',
    description='ICMP tunnel',
    entry_points={
        'console_scripts': [
            'forwarder = forwarder.__main__:start_asyncio_main',
            'proxy = proxy.__main__:start_asyncio_main',
        ],
    },
    install_requires=[
        'protobuf',
    ],
)
