import os, sys
from distutils.core import setup
from glob import glob
import py2exe

# For py2exe & PySide
sys.path.append(os.path.join(os.path.dirname(__file__), "Microsoft.VC90.CRT"))

setup(
    name='VideoTrim',
    version='0.0.1',
    author='Nathan Shearer',
    author_email='shearern@gmail.com',
    url='https://github.com/shearern/SBC-Video-Trimmer',
    package_dir={'': 'src'},
    windows=[
        'src/VideoTrim.pyw'
        ],
    packages=[
        'vidtrim',
        'vidtrim.ui',
        'vidtrim.ffmpeg',
        ],

    # For py2exe & PySide (see http://www.py2exe.org/index.cgi/Tutorial)
    data_files = [("Microsoft.VC90.CRT", glob(r'Microsoft.VC90.CRT\*.*'))]
    )


