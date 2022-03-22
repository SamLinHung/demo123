
@REM initial directory
set python_version=%1%
set dirName=dojo

@REM encrption source code
cd %dirName%
python setup.py build_ext --inplace
dir

@REM copy .pyd
xcopy .\%dirName%\ .

@REM remove not using file & floder
del .\ib.py
del .\ib.c
del .\setup.py

rd /s /q .\build
rd /s /q .\build

dir
