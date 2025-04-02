from setuptools import setup, find_packages

setup(
    name="ev-info-bot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "langgraph",
        "langchain-core",
        "serpapi",
        "requests",
        "beautifulsoup4",
        "python-dotenv",
        "groq"
    ],
) 