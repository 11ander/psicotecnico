import psutil
for n,i in psutil.net_if_addrs().items():
    if n.startswith("wl"):
        for a in i:
            if a.family.name == "AF_INET":
                print(a.address)
