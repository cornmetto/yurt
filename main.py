from vboxmanage import VBoxManage


if __name__ == "__main__":
    vbox = VBoxManage()
    vbox.list("vms")
