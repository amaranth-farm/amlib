from setuptools import setup, find_packages


def scm_version():
    def local_scheme(version):
        return version.format_choice("+{node}", "+{node}.dirty")
    return {
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": local_scheme,
    }

setup(
    name="nmigen-library",
    use_scm_version=scm_version(),
    author="Hans Baier",
    author_email="hansfbaier@gmail.com",
    description="standard library of utility cores for nmigen",
    license="Apache License 2.0",
    setup_requires=["wheel", "setuptools", "setuptools_scm"],
    install_requires=[
        "scipy",
        "nmigen>=0.2,<0.4",
        "importlib_metadata; python_version<'3.8'",
    ],
    packages=find_packages(),
    project_urls={
        "Source Code": "https://github.com/hansfbaier/nmigen-library",
        "Bug Tracker": "https://github.com/hansfbaier/nmigen-library/issues",
    },
)

