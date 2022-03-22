import setuptools

with open("readme.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dojotest",  
    version="0.0.14",
    author="HungYuanLin",
    author_email="slin@dojotechs.com",
    description="A automatic trading application of package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DojoTechs/",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)