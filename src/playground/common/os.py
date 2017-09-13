import subprocess

def getCmdOutput(*args):
    output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return output.stdout

def isPidAlive(pid):
    # This should work for most *nix architectures
    output = getCmdOutput("ps","-p", str(pid))
    lines = output.split(b"\n")
    
    # remove status line
    if len(lines) > 0 and lines[0].strip().lower().startswith(b"pid"):
        lines.pop(0)
    # remove any blank lines
    while len(lines) > 0 and lines[-1].strip() == b"":
        lines.pop(-1)
    if len(lines) == 1:
        return True
    return False
