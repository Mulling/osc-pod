import os
import platform
import getpass

from osc import cmdln
from osc import core
from osc import oscerr


repo2image = {
    'openSUSE_Factory': 'opensuse/tumbleweed',
    'openSUSE_Tumbleweed': 'opensuse/tumbleweed',
}

arch2arch = {
    'x86_64': 'amd64'
}

def get_buildroot(apihost, project, package, repo, arch, vm_type, user=None):
    user = user or ""
    dash_user = f"-{user:s}" if user else ""
    buildroot = core.conf.config["build-root"] % {
        'apihost': apihost,
        'project': project,
        'package': package,
        'repo': repo,
        'arch': arch,
        "user": user,
        "dash_user": dash_user,
    }

    # Taken from osc/build.py
    if vm_type != 'lxc' and vm_type != 'nspawn':
        buildroot = os.path.join(buildroot, '.mount')

    return buildroot

def get_pacdir(buildroot:str, arch: str) -> str:
    pacdir = os.path.join(buildroot, '.build.packages')
    if os.path.islink(pacdir):
        pacdir = os.readlink(pacdir)
        pacdir = os.path.join(buildroot, pacdir)

    return os.path.join(pacdir, 'RPMS', arch)

def store_read_last_buildroot() -> list[str]:
    last_broot = core.store_read_last_buildroot('.')

    if last_broot:
        return last_broot
    else:
        raise oscerr.OscBaseError("Could not find package buildroot")


@cmdln.option('-w', '--workdir', action='store_true',
              help='use volume as the work dir')
@cmdln.option('-r', '--runner', default='podman',
              help='use the specified runner')
@cmdln.option('-v', '--volume', default='/root/rpms',
              help='overwride rpms mount point')
@cmdln.option('-p', '--platform', default='',
              help='use the specified platformstring, i.e., linux/amd64')
def do_pod(self, subcmd, opts, *args):
    """${cmd_name}: Run a container with the build rpms

    Examples:
        osc pod IMAGE   # Run the containr with the IMAGE
                          (default behaviour is to guess
                           the image based on the repo)

    """
    verbose = opts.verbose
    debug = opts.debug

    # TODO: Check if build_root is in the config and act accordingly
    # config_parse = core.conf.get_configParser(opts.conffile)
    # TODO: check for --vm-type=kvm|qemu
    # TODO: check if arch matches for the cases above

    image: str = ''
    target: str = ''
    entrypoint: str = ''

    package = core.store_read_package('.')
    project = core.store_read_project('.')

    repo, arch, runner = store_read_last_buildroot()

    if args and len(args) > 1:
        raise oscerr.WrongArgs("Too many images!")
    elif args:
        image = args[0];
    else:
        # FIXME:
        image = repo2image[repo]

    user = getpass.getuser() if runner in ['podman', 'kvm', 'qemu'] else None
    buildroot = get_buildroot('', project, package,
                              repo, arch, runner, user)

    pacdir = get_pacdir(buildroot, arch)

    # Skip pasing `--platform` if the last build was the same target as us,
    # this makes podman start faster
    if platform.processor() != arch:
        target = f"--platform linux/{arch2arch[arch]}"
    elif opts.platform:
        target = f"--platform {opts.platform}"

    runner = opts.runner
    volume = opts.volume

    if opts.workdir:
        entrypoint = f'-w {volume}'

    if verbose:
        print(f'Running {runner} image {image} with {project}/{package} rpms in {volume}')

    cmd = (f'{runner} run --rm -it -v={pacdir}:{volume} {target} {entrypoint} {image}')

    if debug:
        print(cmd)

    os.system(cmd)
