
@echo off 
setlocal enabledelayedexpansion 

@REM initial directory
set python_version=%1%
set python_version=%python_version:.=%
set dirName=dojotest
set dirName_encrypt_setting=encryption
set dirName_build=\build\lib.win-amd64-cpython

@REM initial file & path
set fileName[0]=ib
set fileName[1]=auth
set fileName[2]=report

set filePath[0]=
set filePath[1]=\base
set filePath[2]=\base



@REM copy setup
echo Process: copy setup
xcopy .\%dirName_encrypt_setting%\ .\%dirName%\


@REM encryption source code
echo Process: encryption source code
cd %dirName%
python setup.py build_ext --inplace
dir

@REM copy .pyd
echo Process: copy .pyd
dir .\build
echo .%dirName_build%-%python_version%\%dirName%\
xcopy .\build\lib.win-amd64-cpython-%python_version%\%dirName%\  .
xcopy .\build\lib.win-amd64-cpython-%python_version%\%dirName%\base  .\base\
dir

@REM remove not using floder
echo Process: remove not using file & floder
del .\setup.py
rd /s /q .\build

rd /s /q .\__pycache__
rd /s /q .\base\__pycache__

@REM remove not using file
set len=0 
:Loop 
if defined fileName[%len%] ( 
	set /a len+=1
	GOTO :Loop 
)
set /a len+=-1
echo %len%

for /l %%n in (0,1,%len%) do ( 
   echo del path: .!filePath[%%n]!\!fileName[%%n]!.py !
   echo del path: .!filePath[%%n]!\!fileName[%%n]!.c !

   del %cd%!filePath[%%n]!\!fileName[%%n]!.py
   del %cd%!filePath[%%n]!\!fileName[%%n]!.c
)

dir
