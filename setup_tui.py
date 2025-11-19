"""Setup script for CyTube TUI Chat Client."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / 'tui_app' / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

setup(
    name='cytube-tui',
    version='0.2.0',
    description='Terminal User Interface for CyTube chat rooms',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='CyTube Bot Contributors',
    url='https://github.com/grobertson/Rosey-Robot',
    packages=['tui_app'],
    package_data={
        'tui_app': [
            'themes/*.json',
            'configs/*.example',
            'README.md',
        ],
    },
    python_requires='>=3.7',
    install_requires=[
        'blessed>=1.19.0',
        'websocket-client>=1.0.0',
        'python-socketio>=5.0.0',
    ],
    entry_points={
        'console_scripts': [
            'cytube-tui=tui_app.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Communications :: Chat',
        'Topic :: Terminals',
    ],
    keywords='cytube chat tui terminal irc blessed',
)
