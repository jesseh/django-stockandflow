from setuptools import setup


setup(
    name='django-stockandflow',
    version='0.0.1',
    description='Django stock and flow tracking for business intelligence metrics',
    long_description = (open('README.rst').read() + 
                        open('CHANGES.rst').read() +
                        open('TODO.rst').read()),
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

