from setuptools import find_packages, setup

package_name = "vr_asr"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Qingyu Geng",
    maintainer_email="yutsin2501@gmail.com",
    description="Speech recognition node (Silero VAD + faster-whisper) for vocal-robot",
    license="MIT",
    entry_points={
        "console_scripts": [
            "vad_node = vr_asr.vad_node:main",
            "asr_node = vr_asr.asr_node:main",
        ],
    },
)
