from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'patrol_main'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'config'), glob(os.path.join('config', '*.*'))),
        (os.path.join('share', package_name, 'maps'), glob(os.path.join('maps', '*.*'))),
    ],
    install_requires=['setuptools', 'requests'],
    zip_safe=True,
    maintainer='CyCle03',
    maintainer_email='cherrybear03@naver.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'patrol_scheduler = patrol_main.patrol_scheduler:main',
            'patrol_node = patrol_main.patrol_node:main',
            'patrol_visualizer = patrol_main.patrol_visualizer:main',
            'obstacle_node = patrol_main.obstacle_node:main',
            'rfid_localization_node = patrol_main.rfid_localization_node:main'
        ],
    },
)
