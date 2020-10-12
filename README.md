# Yurt

Yurt is a command-line tool for creating and managing linux containers on Windows.
It runs LXD in a VirtualBox VM and exposes a selection of LXC commands.

## Installation

We don't have a release for general use at this time. You can test out the current functionality by installing using the [pip](https://pip.pypa.io/en/stable/) package manager. As usual, use a [virtual environment](https://docs.python.org/3/library/venv.html) if possible.

```
pip install git+https://github.com/ckmetto/yurt.git
```

### Requirements
This version of Yurt runs only on Windows.

VirtualBox is required. Download and install it from https://virtualbox.org if you do not already have it installed.

Only Windows 10 and VirtualBox 6 have been tested at this time.

## Usage
After installation, yurt needs to be initialized:

```
yurt init
```
This downloads and imports a virtual appliance file and may take a few minutes to complete.
We also install a network interface on your host to allow for direct communication with containers. Accept the User Account Control prompt from VirtualBox when prompted. Initialization will fail if VirtualBox is denied permission.


After initialization, boot up the VM with:

```
yurt boot
```

Since this will be the first boot, yurt will install and configure LXD in the VM. An active internet connection is needed and the operation may take a few minutes. This is done only on the first boot.

That's it! Now you are ready to launch some containers. The following commands create and start alpine and ubuntu containers respectively.

```
yurt launch alpine/3.11 instance1
yurt launch ubuntu/18.04 instance2
yurt list
```

Run `yurt launch --help` for more information about launching containers and `yurt --help` to see other commands available. At this time, only images from  https://images.linuxcontainers.org are supported.


## Contributing

Please create an issue if something does not work for you.

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgement
Yurt is based on ideas, evaluation and prototyping presented by [Collins Metto](http://arks.princeton.edu/ark:/88435/dsp01v692t925s).

## License
[MIT](https://choosealicense.com/licenses/mit/)
