import subprocess

def getCmdOutput(*args):
    output = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return output.stdout

def isPidAlive(pid):
    # TODO: Support Different Architectures?
    output = getCmdOutput("ps","--no-headers", str(pid))
    return len(output) > 0