# Yurt

Yurt is a command-line tool for creating and managing linux containers on Windows.
It runs LXD in a VirtualBox VM and exposes a selection of LXC commands.


## Installation
### Requirements
This version of Yurt runs only on Windows.

VirtualBox is required. Install from https://virtualbox.org if you do not already have it.

Only Windows 10 and VirtualBox 6 have been tested at this time.

### Install Yurt

We do not have a release yet. You can test out the current functionality by installing using [pip](https://pip.pypa.io/en/stable/). As usual, a [virtual environment](https://docs.python.org/3/library/venv.html) is recommended. You can set one up quickly with [pipenv](https://pypi.org/project/pipenv/).

Create and activate a virtual environment. For example, using pipenv:

```
$ mkdir try-yurt
$ cd ./try-yurt
$ pipenv --three
$ pipenv shell
```

Install yurt:
```
$ pip install git+https://github.com/ckmetto/yurt.git
$ yurt --version
```




## Usage
After installation, initialize yurt with:

```
$ yurt init
```
This downloads and imports a virtual appliance file and may take a few minutes to complete.
We also install a network interface on your host to allow for direct communication with containers. Accept the User Account Control prompt from VirtualBox when it comes up. Initialization will fail if VirtualBox is denied permission.


After initialization, yurt will ask if you want to boot the VM. Respond with 'yes' to start the boot process.
If you choose 'no', you can start it later with:

```
$ yurt boot
```

Since this will be the first boot, yurt will install and configure LXD in the VM. An active internet connection is needed and the operation may take a few minutes. This is done only on the first boot.

That's it! You are now ready to launch some containers. The following commands create and start alpine and ubuntu containers respectively. The containers are assigned with IP addresses that are reachable from the host.

```
$ yurt launch alpine/3.11 instance1
$ yurt launch ubuntu/18.04 instance2
$ yurt list

Name       Status    IP Address       Image
---------  --------  ---------------  -------------------
instance1  Running   192.168.132.117  Alpine/3.11 (amd64)
instance2  Running   192.168.132.92   Ubuntu/bionic (amd64)

```

Run `yurt launch --help` for more information about launching containers and `yurt --help` to explore other commands.

After launching, run `yurt shell <instance> ` to proceed with configuration as you would with any other server.

```
$ yurt shell instance1
root@instance1:~ #
```


## Contributing

Please create an issue if something does not work for you. Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgement
Yurt is based on ideas, evaluation and prototyping presented by [Collins Metto](http://arks.princeton.edu/ark:/88435/dsp01v692t925s) and is inspired by [docker](https://www.docker.com/), [vagrant](https://www.vagrantup.com/), [lxdock](https://github.com/lxdock/lxdock) and, of course, [LXD](https://linuxcontainers.org/lxd/introduction/).

## License
[MIT](https://choosealicense.com/licenses/mit/)
