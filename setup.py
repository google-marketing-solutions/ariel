# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The setup script for Ariel."""

import os
from typing import Final
import setuptools

_CURRENT_DIR: Final[str] = os.path.dirname(os.path.abspath(__file__))


def _get_readme():
  try:
    readme = open(
        os.path.join(_CURRENT_DIR, "README.md"), encoding="utf-8"
    ).read()
  except OSError:
    readme = ""
  return readme


def _get_version():
  with open(os.path.join(_CURRENT_DIR, "ariel", "__init__.py")) as fp:
    for line in fp:
      if line.startswith("__version__") and "=" in line:
        version = line[line.find("=") + 1 :].strip(" '\"\n")
        if version:
          return version
    raise ValueError("`__version__` not defined in `ariel/__init__.py`")


def _parse_requirements(path):
  with open(os.path.join(_CURRENT_DIR, path)) as f:
    return [
        line.rstrip()
        for line in f
        if not (line.isspace() or line.startswith("#"))
    ]


_VERSION: Final[str] = _get_version()
_README: Final[str] = _get_readme()
_INSTALL_REQUIREMENTS: Final[str] = _parse_requirements(
    os.path.join(_CURRENT_DIR, "requirements.txt")
)


setuptools.setup(
    name="gtech-ariel",
    version=_VERSION,
    python_requires=">=3.10",
    description=(
        "Google EMEA gTech Ads Data Science Team's solution to automatically"
        " translate and dub video ads into multiple languages using AI."
    ),
    long_description=_README,
    long_description_content_type="text/markdown",
    author="Google EMEA gTech Ads Data Science Team",
    license="Apache Software License 2.0",
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={"": ["system_settings/*.txt"]},
    install_requires=_INSTALL_REQUIREMENTS,
    url="https://github.com/google-marketing-solutions/ariel",
    keywords=(
        "python ai genai speech-to-text translation text-to-speech video"
        " dubbing youtube gcp"
    ),
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
