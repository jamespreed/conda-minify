# Conda Minify
A simple library to create minified or relaxed versions of Conda environment specs for cross-platform sharing.  

## Why Conda Minify?
It was not an uncommon occurance for me to run into issues when trying to use another team's project.  Although projects were well documented and included an `environment.yaml` file to setup the environment, moving between Windows and Unix made this very difficult.  Several factors were in play:
- Conda packages for Unix and Windows can have different build numbers
- Occassionally packages built for one OS have sub-sub versions that are not available (e.g. "0.11.3.1")
- Lower level dependencies often differ between OS versions
- Often environment specs were just exported "as-is", without thought to which packages were actually needed

## What does Conda Minify do?
Conda Minify provides a simple way to produce an Conda specification YAML file with only the minimum requirements needed to *approximately* reproduce the environment.  Conda can figure out the rest of the details for the dependencies.  For example, if you have an environment with Pandas and Matplotib; sharing the environment really only requires specifying Pandas and Matplotib and their versions.

## Installation
These are the recommended methods for installation.  It is worth noting that Conda Minify can be run *without* installation as a script module using the same CLI commands; please see the [Usage section](####cli-via-python) .
### Via Conda
    conda install conda-minify -c jamespreed
### Via PIP
    pip install conda-minify

## Usage
Conda Minify has two primary method for reducing environment requirements: `minify` and `relax`.  
- `minify` - The primary tool for sharing an environment.  This analyzes the dependency graph for the entire environment and only exports requirements for the "top-level" packages.  I.e. if you created an environment using `conda create -n myenv pandas`, then `minify` would return only `pandas` as the spec.  
- `relax` - An auxilery tool that "loosens" the version requirements.  This allows you convert exact versions specifications to only major, minor, or none at all.  I.e. `scipy=1.3.2` can become `scipy=1.3.*`, or `scipy=1.*` or just `scipy`.  Additional options allow pinning and overriding verions.
### Command Line Interface
After installation the CLI can be invoked using:

    conda-minify <name> <minify | relax> [-f filename] [options ...]

- `name` - environment name to export
- `<minify | relax>` - which tool to use
- `-f filename` - (optional) write the minified spec to `filename` otherwise prints to screen.
- Run the tool to see a full list of options for `minify` and `relax`

#### CLI via Python
Conda Minify is designed to be run as a scripted module in the event that your base Conda installation is locked and prohibits installation of new packages.  Or because you don't want to throw new stuff into your clean Anaconda base environment (I understand).

Clone the repo with git (or download the zip and unzip), move to the top folder of the repo, and run with Python:
```
$> git clone https://github.com/jamespreed/conda-minify.git
$> cd conda-minify
$> pythnon -m conda_minify <name> <minify | relax> [-f filename] [options ...]
```
### Python API
To run this programmatically the Python API provides a relatively easy method.
```python
from conda_minify import CondaEnvironment

# create a CondaEnvironment object for the myenv environment.
cenv = CondaEnvironment(name='myenv')
# build the dependency graph
cenv.build_graph()
# write out the minified version to a file
cenv.minify_requirements(
    export_path='myenv.yaml',
    include=['python'],  # include python so we can set the version
    how='minor'          # relax version requirements to minor releases
)

# OR export the relaxed requirements
cenv.relax_requirements(
    export_path='myenv.yaml',
    how='none',                   # add no versions
    pin=['pandas'],               # except pin the version of pandas i.e. 0.25.3
    override={'python': 'minor'}  # and use the minor version of python i.e. 3.7.*
)
```