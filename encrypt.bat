set python_version=%1%
set dirName=dojo

cd %dirName%
python setup.py build_ext --inplace
dir

cd .\%dirName%\
dir
cd ..

xcopy .\%dirName%\ .
del .\ib.py
del .\ib.c
rd /s /q .\build
del .\setup.py
dir
cd ..
dir