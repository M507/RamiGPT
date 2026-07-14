import re

def get_GOT_ROOT_REGEXPs(hostname):
    GOT_ROOT_REGEXPs = [
        re.compile("^# $"),
        re.compile("^bash-[0-9]+.[0-9]# $"),
        re.compile(f"root@{hostname}:.*#\s")
    ]
    return GOT_ROOT_REGEXPs

def got_root(hostname: str, output: str) -> bool:
    if output is None:
        return False
    text = str(output)
    # Check whole blob first (covers multi-line `id` output).
    if "uid=0(root)" in text:
        return True
    if hostname and f"root@{hostname}:" in text:
        return True

    GOT_ROOT_REGEXPs = get_GOT_ROOT_REGEXPs(hostname or "")
    for line in text.splitlines() or [text]:
        candidate = line.strip("\r")
        # Prompt-style root shells often end with "# " / "#".
        stripped = candidate.strip()
        for pattern in GOT_ROOT_REGEXPs:
            if pattern.fullmatch(candidate) or pattern.fullmatch(stripped + (" " if not stripped.endswith(" ") else "")):
                return True
        if stripped == "#":
            return True
        if hostname and candidate.startswith(f"root@{hostname}:"):
            return True
        if "uid=0(root)" in candidate:
            return True
        if stripped == "root":
            return True
    return False



if __name__ == "__main__":
    print(got_root("pehost", "root@pehost:/home/lowpriv# "))
    