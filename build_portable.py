import subprocess
from generate_version_info import gen_and_write_info

if __name__ == "__main__":
    gen_and_write_info()
    subprocess.run(["pyinstaller", "cli.spec", "cli.py", "--noconfirm", "--clean"])