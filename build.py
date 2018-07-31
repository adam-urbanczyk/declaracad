"""
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the GPL v3 License.

The full license is in the file COPYING.txt, distributed with this software.

Created on Jan 12, 2018

@author
"""
import sh
import os
import sys
import textwrap
from glob import glob
from contextlib import contextmanager

CONTROL_TEMPLATE = """
Package: {name}
Section: {section}
Architecture: all
Maintainer: {maintainer}
Standards-Version: 4.0.0
Homepage: {homepage}
Depends: {depends}
Priority: optional
Version: {version}
Description: {short_desc}
 {full_desc}

"""

@contextmanager
def cd(path):
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def make_installer(cfg):
    """ """
    print("Building installer...")
    build_dir = 'build/{name}-{version}'.format(**cfg)
    cfg.update({'build_dir': build_dir})
    install_dir = '{build_dir}/usr/share/{name}'.format(**cfg)
    desktop_dir = '{build_dir}/usr/share/applications/'.format(**cfg)
    cfg.update({'install_dir': install_dir,
                'desktop_dir': desktop_dir})

    os.makedirs(build_dir)

    with cd(build_dir):
        os.makedirs('DEBIAN')

        #: Write control
        with open('DEBIAN/control', 'w') as f:
            f.write(CONTROL_TEMPLATE.format(**cfg))

    #: Write
    os.makedirs(install_dir)
    print(sh.cp('-R', glob('build/exe.linux-x86_64-3.5/*'), install_dir))

    #: Make a simlink to /usr/local/bin
    #print(sh.ln('-sf', '{install_dir}/{name}'.format(**cfg),
    #            '{install_dir}/usr/local/bin/{name}'.format(**cfg)))

    #: Make a desktop icon /usr/share/applications
    os.makedirs(desktop_dir)
    print(sh.cp('{name}/res/declaracad.desktop'.format(**cfg), desktop_dir))

    #: Prepare
    try:
        print(sh.chown('-R', 'root:root', build_dir))
    except:
        pass

    #: Build it
    deb = sh.Command('dpkg-deb')
    print(deb('--build', build_dir))


def main(cfg):
    """ Build and run the app
    
    """
    try:
        #: Clean
        print("Clean...")
        sh.rm('-R', glob('build/*'))
    except:
        pass

    #: Build
    print("Build...")
    print(sh.python('release.py', 'build'))

    #: Enter build
    print("Trim...")
    with cd('build/exe.linux-x86_64-3.5/'):
        #: Trim out crap that's not needed
        for p in [
                #'libicu*',
                'lib/PyQt5/Qt',
                'lib/PyQt5/QtB*',
                'lib/PyQt5/QtDes*',
                'lib/PyQt5/QtH*',
                'lib/PyQt5/QtL*',
                'lib/PyQt5/QtM*',
                'lib/PyQt5/QtN*',
                'lib/PyQt5/QtPos*',
                'lib/PyQt5/QtT*',
                'lib/PyQt5/QtO*',
                'lib/PyQt5/QtSe*',
                'lib/PyQt5/QtSq*',
                'lib/PyQt5/QtQ*',
                'lib/PyQt5/QtWeb*',
                'lib/PyQt5/QtX*',
                #'platforms',
                #'imageformats',
                'libQt5Net*',
                'libQt5Pos*',
                'libQt5Q*',
                'libQt5Sq*',
                'libQt5O*',
                'libQt5T*',
                'libQt5Web*',
                #'declaracad',
                'libQt5X*'
                ]:
            try:
                sh.rm('-R', glob(p))
            except Exception as e:
                print(e)

        #: Test the app
        print("Launching...")
        cmd = sh.Command('./{name}'.format(**cfg))
        print(cmd())

    #: If good then build installer
    make_installer(cfg)

if __name__ == '__main__':
    cfg = {
        'name': 'declaracad',
        'version': 1.0,
        'maintainer': 'CodeLV <frmdstryr@gmail.com>',
        'section': 'engineering',
        'depends': '',
        'homepage': 'https://github.com/codelv/declaracad',
        'short_desc': 'A declarative and parametric 3D modeling application',
        'full_desc': "\n ".join(textwrap.dedent(
            """
            Written using python and enaml.
            """.strip()).split("\n")),
    }
    main(cfg)
