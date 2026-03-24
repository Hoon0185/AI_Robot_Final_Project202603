from setuptools import find_packages, setup
import os

package_name = 'patrol_main'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), ['launch/patrol.launch.py']),
        (os.path.join('share', package_name, 'config'), ['config/shelf_coords.yaml']),
    ],
    install_requires=['setuptools'],
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
            'patrol_node = patrol_main.patrol_node:main'
        ],
    },
)
