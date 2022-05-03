from distutils.core import setup
from Cython.Build import cythonize
setup(
    name='Hello world app',
    package_dir={'cython_test': ''},
    ext_modules=cythonize(["ib.py",
                           "base/auth.py"])
    
    )