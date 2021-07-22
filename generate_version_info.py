from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringStruct, StringTable, \
    VarFileInfo, VarStruct

from subot.utils import read_version
from configparser import ConfigParser


def generate_version_info():
    config = ConfigParser()
    config.read("setup.cfg")
    custom = config["custom"]
    product_name = custom["product_name"]
    internal_name = custom["internal_name"]
    exe_name = custom["exe_name"]

    version = read_version()

    # UTF-8
    #
    # For more details about fixed file info 'ffi' see:
    # http://msdn.microsoft.com/en-us/library/ms646997.aspx
    VERSION = tuple(int(i) for i in version.split('.') + ['0'])
    VERSION_DOTTED = f"{VERSION[0]}.{VERSION[1]}.{VERSION[2]}.{VERSION[3]}"
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
            # Set not needed items to zero 0.
            filevers=VERSION,
            prodvers=VERSION,
            # Contains a bitmask that specifies the valid bits 'flags'r
            mask=0x3f,
            # Contains a bitmask that specifies the Boolean attributes of the file.
            flags=0x0,
            # The operating system for which this file was designed.
            # 0x4 - NT and there is no need to change it.
            OS=0x40004,
            # The general type of file.
            # 0x1 - the file is an application.
            fileType=0x1,
            # The function of the file.
            # 0x0 - the function is not defined for this fileType
            subtype=0x0,
            # Creation date and time stamp.
            date=(0, 0)
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        u'040904B0',
                        [StringStruct(u'CompanyName', u'Alex Gurganus'),
                         StringStruct(u'FileDescription', u'Accessibility helper for Siralim Ultimate'),
                         StringStruct(u'FileVersion', VERSION_DOTTED),
                         StringStruct(u'InternalName', internal_name),
                         StringStruct(u'LegalCopyright', u''),
                         StringStruct(u'OriginalFilename', exe_name),
                         StringStruct(u'ProductName', product_name),
                         StringStruct(u'ProductVersion', VERSION_DOTTED)])
                ]),
            VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
        ]
    )
    return version_info

def write_version_info(filename: str, version_info: VSVersionInfo):
    with open(filename, "w+") as f:
        f.writelines([str(version_info)])

def gen_and_write_info():
    version_info = generate_version_info()
    write_version_info('file_version_info.py', version_info)

if __name__== "__main__":
    gen_and_write_info()
