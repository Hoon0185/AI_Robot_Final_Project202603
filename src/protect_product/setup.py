import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'protect_product'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # ('share/' + package_name + '/models', ['models/products.pt', 'models/product.db']), #model(trainmodel, testdb)
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))), #launch
        (os.path.join('share', package_name, 'models'), glob('models/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='bird99',
    maintainer_email='bird99@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            #'detect_product=protect_product.detect_product:main',
            #'detector = protect_product.detector:main',
            'product_detector = protect_product.product_detector:main',
            'qr_detector = protect_product.qr_detector:main',
            'verifier = protect_product.verifier:main',
            'viewer = protect_product.viewer:main',
            'camera_node = protect_product.camera_node:main',
            'camera = protect_product.camera:main',
        ],
    },
)
