from setuptools import setup

setup(
    name='cosmicops',
    version='0.1.13',
    packages=['cosmicops', 'cosmicops.objects'],
    url='https://github.com/MissionCriticalCloud/cosmicOps',
    license='Apache-2.0',
    author='Kristian Vlaardingerbroek',
    author_email='kvlaardingerbroek@schubergphilis.com',
    description='Handy tools to operate a Cosmic cloud',
    python_requires='>=3.6',
    install_requires=[
        'click-spinner',
        'libvirt-python',
        'fabric',
        'cs',
        'slack-webhook',
        'PyMySQL',
        'python-hpilo'
    ]
)
