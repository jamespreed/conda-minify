from setuptools import setup
from pathlib import Path

here = Path(__file__).parent.absolute()

with here.joinpath('README.md').open() as fp:
    long_description = fp.read().strip()

with here.joinpath('VERSION').open() as fp:
    VERSION = fp.read().strip()

setup(
    name='conda-reduce',
    version=VERSION,  
    description='A simple library to create minified or relaxed versions '
                'of Conda environment specs for cross-platform sharing.', 
    long_description=long_description, 
    long_description_content_type='text/markdown',  
    url='https://github.com/jamespreed/conda-reduce',
    author='James Reed',
    author_email='https://github.com/jamespreed/conda-reduce/issues', 
    classifiers=[  
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='conda virtual environment yaml',
    packages=['conda_reduce']
    python_requires='>=3.4, <4',
    install_requires=['conda>=4.3.0'],
    entry_points={  # Optional
        'console_scripts': [
            'conda-reduce = conda_reduce.__main__:main',
        ],
    },
)