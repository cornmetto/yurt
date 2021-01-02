# Yurt

`yurt` simplifies the setup and management of Linux containers on Windows. It runs [LXD](https://linuxcontainers.org/lxd/introduction/) in a VirtualBox VM and exposes basic container management commands.

![Basic Usage](./docs/images/usage.gif)

## Installation
### Requirements
This version of Yurt works only on Windows. MacOS support is on the roadmap.

VirtualBox is required. Install from https://virtualbox.org if you do not already have it.

Only Windows 10 and VirtualBox 6 have been tested at this time.

### Installation

Although we do not have a release yet, you can test out the current functionality using either [pipx](https://pipxproject.github.io/pipx/installation/) or [pip](https://pip.pypa.io/en/stable/). Python 3.6+ is required.

#### 1. Using pipx.

Assuming you have already installed [pipx](https://pipxproject.github.io/pipx/installation/):
```
$ pipx install git+https://github.com/ckmetto/yurt.git
```

#### 2. Using pip.
With [pip](https://pip.pypa.io/en/stable/), a Virtual Environment is recommended. This example uses [pipenv](https://pypi.org/project/pipenv/) to create one:


```
# Create and activate a Virtual Environment.

$ mkdir try-yurt
$ cd ./try-yurt
$ pipenv --three
$ pipenv shell


# Install yurt.

$ pip install git+https://github.com/ckmetto/yurt.git
```

Yurt should be available on your PATH after installing using either of these options.
```
$ yurt --version
```
You will have to activate the virtual environment each time you need to use yurt in case you went with option 2.



## Usage
After installation, initialize your instance with:

```
$ yurt init
```
This downloads and imports a virtual appliance file and may take a few minutes to complete.
We also install a network interface on your host to allow for direct communication with containers. Accept the User Account Control prompt from VirtualBox when it comes up. Initialization will fail if VirtualBox is denied permission.


That's all. You are now ready to launch some containers. At this time we support amd64 images from https://images.linuxcontainers.org/ only. Run `yurt images --remote` to view them.

```
$ yurt launch alpine/3.11 c1
$ yurt launch ubuntu/18.04 c2
$ yurt list

Name       Status    IP Address       Image
---------  --------  ---------------  -------------------
c1  Running   192.168.132.117  Alpine/3.11 (amd64)
c2  Running   192.168.132.92   Ubuntu/bionic (amd64)

```

After launching, start a shell in the container with `yurt shell <name>` . The terminal launched by this command is not very sophisticated 
so it's best to configure a user to SSH with.


See `yurt -h` for more information about the CLI.

## Contributing

To get started:
```
$ git clone https://github.com/ckmetto/yurt.git
$ cd yurt
$ pip install -e .
$ export YURT_ENV=dev
$ yurt init
```

`YURT_ENV=dev` makes yurt set up a separate VM for development. When set, all commands refer to this development VM.
Similarly, you can set `YURT_ENV=test` to run tests in yet another separate VM with `python -m unittest`.

Please create an issue if something does not work for you. Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgement
Yurt is based on ideas, evaluation and prototyping presented by [Collins Metto](http://arks.princeton.edu/ark:/88435/dsp01v692t925s) and is inspired by [docker](https://www.docker.com/), [vagrant](https://www.vagrantup.com/), [lxdock](https://github.com/lxdock/lxdock) and [LXD](https://linuxcontainers.org/lxd/introduction/).

## License
[MIT](https://choosealicense.com/licenses/mit/)
