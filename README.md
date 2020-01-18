# Conda Minify
A simple library to create minified or relaxed versions of Conda environment specs for cross-platform sharing.  

## Why Conda Minify?
It was not an uncommon occurance for me to run into issues when trying to use another team's project.  Although projects were well documented and included an `environment.yaml` file to setup the environment, moving between Windows and Unix made this very difficult.  Several factors were in play:
- Conda packages for Unix and Windows can have different build numbers
- Occassionally packages built for one OS have sub-sub versions that are not available (e.g. "0.11.3.1")
- Lower level dependencies often differ between OS versions
- Often environment specs were just exported "as-is", without thought to which packages were actually needed

## What does Conda Minify do?
Conda Minify provides a simple way to produce an environment specification YAML file wiht only the minimum requirements needed to approximately reproduce the environment.  After that, Conda can figure out the rest of the details for the dependencies.  For example, if you have an environment with Pandas and Matplotib; sharing the environment really only requires specifying Pandas and Matplotib and their versions.

## Installation
### Via Conda
    conda install 

### Via PIP
    pip

## Usage
### CLI
(TODO)
### Python API
(TODO)