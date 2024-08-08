from setuptools import setup

setup(
    name="pycdft",
    version="1.0",
    author="He Ma, Wennie Wang, Siyoung Kim, Man Hin Cheng, Marco Govoni, Giulia Galli",
    author_email="mahe@uchicago.edu",
    packages=[
        "pycdft",
        "pycdft.atomic",
        "pycdft.common",
        "pycdft.constraint",
        "pycdft.debug",
        "pycdft.dft_driver",
        "pycdft.elcoupling"
    ],
    install_requires=[
        "ase",
        "numpy",
        "scipy",
        "pyFFTW",
        "lxml"
    ],
)
