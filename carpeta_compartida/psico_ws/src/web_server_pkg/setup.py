from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

# Indicamos a catkin que el paquete Python 'web_server_pkg'
# está dentro del directorio 'src'
d = generate_distutils_setup(
    packages=['web_server_pkg'],
    package_dir={'': 'src'},
)

setup(**d)
