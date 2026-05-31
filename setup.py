from setuptools import setup, find_packages

setup(
    name="research-report-monitor",
    version="1.0.0",
    description="Research report monitor - auto search & download AI/semiconductor reports",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "requests>=2.28.0",
        "pyyaml>=6.0",
        "schedule>=1.2.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "notify": ["plyer>=2.1.0"],
    },
    entry_points={
        "console_scripts": [
            "yanbao=main:main",
        ],
    },
)
