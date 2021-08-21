# -*- mode: python ; coding: utf-8 -*-
from configparser import ConfigParser


config = ConfigParser()
config.read('setup.cfg')

program_name = config["custom"]["product_name"]
internal_name = config["custom"]["internal_name"]
block_cipher = None


a = Analysis(['cli.py'],
             pathex=['C:\\Users\\Alex Gurganus\\PycharmProjects\\SiralimUltimateBot'],
             binaries=[],
             datas=[
             ('VERSION', '.'),
             ('assets.db', '.'),
             ('resources/audio', 'resources/audio'),
             ('resources/assets_padded/NPCs/Castle', 'resources/assets_padded/NPCs/Castle'),
             ('resources/assets_padded/floortiles', 'resources/assets_padded/floortiles'),
             ('resources/extracted_assets/floortiles', 'resources/extracted_assets/floortiles'),
             ('resources/extracted_assets/generic/floor_standard1_0.png', 'resources/extracted_assets/generic'),
             ('resources/extracted_assets/underwater_overlay_0.png', 'resources/extracted_assets'),
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=["hooks/hook.py"],
             excludes=['tkinter', 'notebook', 'nbconvert', 'nbformat', 'markupsafe', 'jedi', 'IPython'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name=internal_name,
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False,
          version='file_version_info.py',
          )


a.binaries = a.binaries - TOC([('cv2\opencv_videoio_ffmpeg453_64.dll', None, None)])

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name=program_name)
