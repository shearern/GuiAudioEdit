import os
import sys
import subprocess

# == Setup builders ==========================================================

python = sys.executable

uic = Builder(action = 'c:\Python27\Scripts\pyside-uic.exe $SOURCE -o $TARGET')
qrc = Builder(action = 'c:\Python27\Lib\site-packages\PySide\pyside-rcc.exe $SOURCE -o $TARGET')
py2exe_builder = Builder(action = python + ' setup.py py2exe')

env = Environment(
    BUILDERS = {
        'UiClass' : uic,
        'QtResources': qrc,
        'Exe': py2exe_builder,
    },
#    ENV = {'PATH' : os.environ['PATH']}
    )

# == Utiltities ==============================================================

def list_files_in(root, extensions=None):
    for filename in os.listdir(root):
        path = os.path.join(root, filename)
        if os.path.isfile(path):
            if extensions is None:
                yield path
            else:
                for ext in extensions:
                    if path.lower().endswith(ext.lower()):
                        yield path
        elif os.path.isdir(path):
            for sub_path in list_files_in(path, extensions):
                yield sub_path



# == Builds ==================================================================

built_source_files = list()

# Convert .ui files to .py
ui_paths = list(list_files_in('src', ('.ui', )))
print "UI Files:"
for ui_path in ui_paths:
    print " -", ui_path
    ui_py_path = ui_path[:-3] + '.py'
    built_source_files.append(env.UiClass(ui_py_path, ui_path))

# Generate Qt Resource files
rc_asset_files = list(list_files_in('src', ('.png', '.jpg', '.gif',)))
print "Qt RC Asset Files:"
for rc_asset_file in rc_asset_files:
    print " -", rc_asset_file
built_source_files.append(env.QtResources('src/vidtrim/ui/qt_assets_rc.py', ['src/vidtrim/ui/qt_assets.qrc', ] + rc_asset_files))

# Alias for source files
env.Alias('built_source_files', built_source_files)

# Generate distribution file
py_files = list(list_files_in('src', ('.py', '.pyw')))
py_files.append('setup.py')
print "Python Source Files:"
for py_file in py_files:
    print ' -', py_file
env.Exe('dist/Vid Trimmer.exe', py_files)
