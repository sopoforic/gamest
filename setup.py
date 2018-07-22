from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name="gamest",
    description="Tracks game play time.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/sopoforic/gamest',
    author="Tracy Poff",
    author_email="tracy.poff@gmail.com",
    include_package_data=True,
    packages=['gamest', 'gamest_plugins'],
    install_requires=['sqlalchemy', 'psutil', 'requests', 'appdirs'],
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
    entry_points={
        'gui_scripts': [
            'gamest = gamest.app:main',
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Topic :: Games/Entertainment",
    ],
)
