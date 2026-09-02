from setuptools import find_packages, setup
import os
from glob import glob

package_name = "vr_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "config", "pipewire"), glob("config/pipewire/*.conf")),
        (os.path.join("share", package_name, "data"), glob("data/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Qingyu Geng",
    maintainer_email="yutsin2501@gmail.com",
    description="Launch files and configuration for the vocal-robot stack",
    license="MIT",
    entry_points={
        "console_scripts": [],
    },
)
