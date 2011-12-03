from setuptools import setup


long_description = (open('README.rst').read() + 
                    open('CHANGES.rst').read() +
                    open('TODO.rst').read())

setup(
    name='django-stockandflow',
    version='0.0.4',
    description='Django stock and flow tracking for business intelligence metrics',
    long_description = long_description,
    author='Jesse Heitler',
    author_email='jesseh@i-iterate.com',
    url='http://github.com/jesseh/django-stockandflow/',
    packages=['stockandflow',],
    license='LICENSE.txt',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    zip_safe=False,
)

