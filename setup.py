"""Setup script for python_logger_system"""

from setuptools import setup, find_packages
from pathlib import Path

readme = Path(__file__).parent / "README.md"
long_description = readme.read_text(encoding="utf-8") if readme.exists() else ""

setup(
    name="python-logger-system",
    version="1.0.0",
    author="kcenon",
    author_email="kcenon@naver.com",
    description="High-performance asynchronous logging framework for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kcenon/python_logger_system",
    packages=find_packages(exclude=["tests", "examples", "docs"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0", "black>=23.0.0"],
        "security": ["cryptography>=41.0.0"],
    },
)
