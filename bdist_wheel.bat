@REM dist package
echo dist package
python setup.py sdist
python setup.py sdist bdist_wheel
dir
