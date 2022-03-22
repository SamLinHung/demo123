set python_version=%1%
set dirName=dojo

cd %dirName%
python37 setup.py build_ext --inplace
dir
xcopy .\build\lib.win-amd64-%python_version%\%dirName%\ .
del .\ib.py
del .\ib.c
cd ..