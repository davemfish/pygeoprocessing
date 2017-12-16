"""setup.py module for PyGeoprocessing."""
from Cython.Build import cythonize
import numpy
from setuptools.extension import Extension
from setuptools import setup
import pkg_resources

# Read in requirements.txt and populate the python readme with the non-comment
# contents.
_REQUIREMENTS = [
    x for x in open('requirements.txt').read().split('\n')
    if not x.startswith('#') and len(x) > 0]
README = open('README.rst').read().format(
    requirements='\n'.join(['    ' + r for r in _REQUIREMENTS]))


def requirements(*pkgnames):
    """Get individual package requirements from requirements.txt.

    This is particularly useful for keeping requirements.txt the central
    location for a required package's version specification, so the only thing
    that needs to be specified here in setup.py is the package name.

    Parameters:
        pkgnames (strings): Optional.  Package names, provided as individual
            string parameters.  If provided, only requirements matching
            these packages will be returned.  If not provided, all package
            requirements will be returned.

    Returns:
        A list of package requirement strings, one for each package name
        parameter.

    Raises:
        ValueError: When a packagename requested is not in requirements.txt
    """
    desired_pkgnames = set(pkgnames)

    found_pkgnames = {}
    with open('requirements.txt') as requirements:
        for line in requirements:
            try:
                package_req = pkg_resources.Requirement.parse(line)
            except ValueError:
                continue
            else:
                project_name = package_req.project_name
                if project_name in desired_pkgnames:
                    found_pkgnames[project_name] = str(package_req)

    if len(desired_pkgnames) != len(found_pkgnames):
        missing_pkgs = desired_pkgnames - set(found_pkgnames.keys())
        raise ValueError(('Could not find package '
                          'requirements for %s') % list(missing_pkgs))
    return found_pkgnames.values()


BUILD_REQUIREMENTS = ['cython'] + requirements()

setup(
    name='pygeoprocessing',
    description="PyGeoprocessing: Geoprocessing routines for GIS",
    long_description=README,
    maintainer='Rich Sharp',
    maintainer_email='richpsharp@gmail.com',
    url='https://bitbucket.org/natcap/pygeoprocessing',
    packages=[
        'pygeoprocessing',
        'pygeoprocessing.routing',
        'pygeoprocessing.testing',
    ],
    package_dir={
        'pygeoprocessing': 'src/pygeoprocessing'
    },
    natcap_version='src/pygeoprocessing/version.py',
    include_package_data=True,
    install_requires=BUILD_REQUIREMENTS,
    setup_requires=requirements(),
    license='BSD',
    zip_safe=False,
    keywords='gis pygeoprocessing',
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: Scientific/Engineering :: GIS',
        'License :: OSI Approved :: BSD License'
    ],
    ext_modules=cythonize(
        [Extension(
            "pygeoprocessing.routing.routing",
            ["src/pygeoprocessing/routing/routing.pyx"],
            include_dirs=[
                numpy.get_include(),
                'src/pygeoprocessing/routing'],
            language="c++")]),
)
