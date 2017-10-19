from setuptools import setup, find_packages

setup(
    name='flask-graphql-rest',
    version='0.0.0',
    packages=find_packages(exclude=['*tests*']),
    url='',
    license='',
    author='',
    author_email='',
    description='',
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    install_requires=[
        'Flask==0.12.2',
        'flask-sqlalchemy==2.3.1',
        'graphene>=2.0.dev',
        'graphene-sqlalchemy>=2.0.dev',
        'graphql-server-core>=1.0.dev'
    ],
    classifiers=[
        'License :: Private :: Do Not Publish'
    ]
)
