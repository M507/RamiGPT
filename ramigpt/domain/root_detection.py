import re

def get_GOT_ROOT_REGEXPs(hostname):
    GOT_ROOT_REGEXPs = [
        re.compile("^# $"),
        re.compile("^bash-[0-9]+.[0-9]# $"),
        re.compile(f"root@{hostname}:.*#\s")
    ]
    return GOT_ROOT_REGEXPs

def got_root(hostname: str, output: str) -> bool:
    GOT_ROOT_REGEXPs = get_GOT_ROOT_REGEXPs(hostname)
    for i in GOT_ROOT_REGEXPs:
        if i.fullmatch(output):
            return True
    if output.startswith(f'root@{hostname}:'):
        return True
    if f"root@{hostname}:" in output:
        return True
    if "uid=0(root)" in output:
        return True
    if "root" == output:
        return True
    return False



if __name__ == "__main__":
    print(got_root("pehost", "root@pehost:/home/lowpriv# "))
    