import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Folketing_scraper", # Replace with your own username
    version="1.0",
    author="Malthe Karbo",
    author_email="Malthekarbo@gmail.com",
    description="A simple package which allows scraping of www.ft.dk",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mkarbo/folketing_scraper",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)